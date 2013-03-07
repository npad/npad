#! /usr/bin/python -u
#! /usr/bin/env python

# choose launch: env is more portable or -u for unbuffered Logs

import os
import sys
import socket
import SocketServer
import exceptions
import thread
import threading
import time
import optparse
import pwd
import re
import traceback
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

import Traffic

from DiagServer import *

VERSION = 0

from DiagServerConfig import MAX_SOURCESINK_TIME
from DiagServerConfig import WATCHDOG_TIME
from DiagServerConfig import PATHDIAG_PATH
from DiagServerConfig import MKDATASUMMARY_PATH
from DiagServerConfig import LOGBASE_URL
from DiagServerConfig import LOGBASE_FILE
from DiagServerConfig import CONTROL_ADDR
from DiagServerConfig import CONTROL_PORT
from DiagServerConfig import WC_PATH
try:
	from DiagServerConfig import WWW_SERVER
except:
	WWW_SERVER = True
try:
	from DiagServerConfig import WWW_PORT
	from DiagServerConfig import WWW_DIR
	have_www_config = WWW_SERVER
except:
	have_www_config = False
from DiagServerConfig import TEST_PORTRANGE_MIN
from DiagServerConfig import TEST_PORTRANGE_MAX
try:
	from DiagServerConfig import THREADS
except:
	THREADS = 1

test_portrange_current = TEST_PORTRANGE_MAX

def testrange_bind(sock, name):
	global test_portrange_current
	done = False
	starting_port = test_portrange_current
	while not done:
		test_portrange_current = test_portrange_current+1
		if test_portrange_current > TEST_PORTRANGE_MAX:
			test_portrange_current = TEST_PORTRANGE_MIN
		try:
			sock.bind((name, test_portrange_current))
			done = True
		except Exception, e:
			if starting_port == test_portrange_current:
				print_exc() # XXX debugging (fatal anyhow)
				raise e
	print("Bound port: %d"%test_portrange_current);

	
class ControlProtocolError(exceptions.Exception):
	def __init__(self, msg):
		self.msg = msg
	
	def __str__(self):
		return self.msg

class DiagStats():
	# Be aware these are not protected by locks
	requests = 0
	queued = 0
	punted = 0
	maxqlen = 0
	maxqtime = 0
	noreport = 0
	died = 0
	completed = 0

	def show(self):
		return("R %d Q %d P %d Ql %d Qt %d NO %d DI %d CO %d\n"%
		       (self.requests, self.queued, self.punted, 
			self.maxqlen, self.maxqtime,
			self.noreport, self.died, self.completed ))

global stats
stats=DiagStats()

# list of regular expressions to match extra_args that may be passed from the client to pathdiag
validargs = [
	"--tos=0x20", # scavenger service, safe for public use
#	"--tos=[x0-9A-Fa-f]*$"	# generic tos, not safe on all networks  XXX
	]

class DiagRequestHandler(SocketServer.StreamRequestHandler):
	# For the watchdog
	test_start_time = None
	kill_test = None
	kill_test_args = None

	# Add to the list of waiting tests.
	# Ensures there can be only one test running at a time.
	def test_list_add(self):
		self.server.test_list_cv.acquire()
		self.server.test_list.append(self)
		if len(self.server.test_list) > stats.maxqlen:
			stats.maxqlen = len(self.server.test_list)
		print("Queue position: %d"%len(self.server.test_list))
		while self.server.test_list.index(self) > THREADS-1:
			# Notify the client of their position in line.
			try:
				self.wfile.write("queue_depth %d\n"%self.server.test_list.index(self))
			except: # client must be gone
				self.server.test_list_cv.release() 
				self.test_list_remove()
				return False
			self.server.test_list_cv.wait(60.0) # Timeout to mask notifyAll() race
		self.server.test_list_cv.release()
		return True
	
	# Remove from the list of waiting tests.
	def test_list_remove(self):
		self.server.test_list_cv.acquire()
		del self.server.test_list[self.server.test_list.index(self)]
		if len(self.server.test_list) > 0:
			self.server.test_list_cv.notifyAll()
		self.server.test_list_cv.release()
	
	
	# Handle the initial handshake (version exchange)
	def do_handshake(self, cmd):
		if cmd[0] != "handshake":
			raise ControlProtocolError("Malformed handshake")
		try:
			client_version = int(cmd[1])
		except (ValueError, IndexError):
			raise ControlProtocolError("Malformed handshake")
		self.wfile.write("handshake %d\n"%VERSION)
		print("%s: Handshake good: %s"%(str(self.client_address), " ".join(cmd[1:])))
	
	
	def kill_source_sink(self, ts):
		print(ts.sock.close())
	
	# Handle the test_source/sink commands
	def do_source_sink(self, cmd):
		try:
			secs = int(cmd[1])
			if secs > MAX_SOURCESINK_TIME:
				secs = MAX_SOURCESINK_TIME
				self.wfile.write("warn Using test time %d instead of %s\n"%(secs, cmd[1]))
		except:
			raise ControlProtocolError("Bad %s arguments"%cmd[0])
		
		ts = Traffic.TrafficSock()
		self.test_start_time = time.time()
		self.kill_test = self.kill_source_sink
		self.kill_test_args = (ts,)
		if not self.test_list_add():
			self.kill_test = None
			self.kill_test_args = None
			return
		self.test_start_time = time.time() # don't short test their queueing time
		
		try:
			try:
				testrange_bind(ts.sock, self.request.getsockname()[0])
				ts.sock.listen(1)
				self.wfile.write("listen %s %d\n"%(ts.sock.getsockname()[0:2]))
			except Exception, e:
				self.wfile.write("warn While binding socket, got error: %s\n"%e)
				raise e
			 
			try:
				ts.passive_open(self.client_address[0])
				if cmd[0] == "test_sink":
					ts.sink(maxtime=secs)
				else:
					ts.source(maxtime=secs)
				ts.sock.close()
			except:
				self.wfile.write("warn Got exception while running test\n")
			self.wfile.write("report none\n")
		except: pass
		
		self.kill_test = None
		self.kill_test_args = None
		self.test_list_remove()
	
	
	# Handle the test_pathdiag command
	def do_pathdiag(self, cmd, xargs=[]):
		now =  time.gmtime()
		dir = time.strftime("/Reports-%Y-%m", now)
		relative = "/%s-%s"%(self.request.getpeername()[0], \
		                          time.strftime("%Y-%m-%d-%H:%M:%S", now))
		try:
			os.mkdir(LOGBASE_FILE + dir)
		except OSError, e:
			if e[0] != 17:
				raise e
		log_file = LOGBASE_FILE + dir + relative
		log_url = LOGBASE_URL + dir + relative + ".html"

		try:
			rtt = int(cmd[1])
			rate = int(cmd[2])
			if rtt < 1 or rate < 1:
				raise Error()
		except:
			self.wfile.write("error Bad pathdiag arguments\n") 
			raise ControlProtocolError("Bad pathdiag arguments")

		self.test_start_time = time.time()
		stats.queued += 1
		print("Thread queued: %s"%relative)
		if not self.test_list_add():  # stalls, waiting for my turn
			self.kill_test = None
			self.kill_test_args = None
			stats.punted += 1
			print("Thread punted: %s"%relative)
			return
		qtime = time.time() - self.test_start_time
		self.test_start_time = time.time() # don't short the test by their queueing time
		if qtime > stats.maxqtime:
			stats.maxqtime = qtime
		print("Thread test start %s (queue time %d)"%(relative, qtime))

		# open a per run logfile
		logf=open(log_file + ".out", "w")
		logf.write("Start")

		pid = -1
		try:

			(r, w) = os.pipe()
			pid = os.fork()
			if pid == 0:
				try:
					# Create a socket on an ephemeral port for pathdiag
					# we do this first, so print goes to the shared log
					ts = Traffic.TrafficSock()
					testrange_bind(ts.sock, self.request.getsockname()[0])

					# Set up stdout/err to the pipe.  All further output goes to the cleint
					os.dup2(w, 1)
					os.dup2(w, 2)
					os.close(w)

					# listen and tell the client
					ts.sock.listen(1)
					self.wfile.write("listen %s %d\n"%(ts.sock.getsockname()[0:2]))
					ts.passive_open(self.client_address[0])

					# don't hold the listen FD in case we are going to be restarted
#					os.close(self.socket.fileno())
					os.close(3) # XXXX - I can't find the FD in a good way
					
					args = [ PATHDIAG_PATH, str(rtt), str(rate) ]
					args[1:1] = xargs
					args[1:1] = ["-F%d"%ts.sock.fileno(), "-x", \
						"-l%s"%log_file, "--plot=yes", "--maxtime=%d"%WATCHDOG_TIME ]
					
					env = os.environ
					try:
						env['PYTHONPATH'] = env['PYTHONPATH'] + ":" + WC_PATH
					except:
						env['PYTHONPATH'] = WC_PATH
					os.execve(args[0], args, env)
				except Exception, e:
					logf.write("child error %s\n%s\n"%(str(e),traceback.format_exc()))
					self.wfile.write("child error %s\n%s\n"%(str(e),traceback.format_exc()))
					os._exit(1)
				# child ends here
			os.close(w)
			rf = os.fdopen(r)
			
			self.kill_test = os.kill
			self.kill_test_args = (pid, 9)
			
			line = rf.readline()
			while len(line) > 0:
				logf.write(line)
				self.wfile.write("info %s"%line)
				line = rf.readline()
			if os.access(log_file + ".html", os.R_OK):
				logf.write("report url %s\n"%log_url)
				self.wfile.write("report url %s\n"%log_url)
			else:
				logf.write("error Pathdiag failed to generate report.\n")
				self.wfile.write("error Pathdiag failed to generate report.\n")
				stats.noreport += 1
				print("Thread noreport %s"%relative)
		except Exception, e:
			stats.died += 1
			print("Thread died %s"%relative)
			try:
				logf.write("error %s\n"%str(e))
				self.wfile.write("error %s\n"%str(e))
			except Exception, e:
				logf.write("unable to report error to client: %s\n"%str(e))
				print("unable to report error to client: %s\n"%str(e))
		if pid > 0:
			try:
				(wpid, status) = os.waitpid(pid, 0)
			except:
				print("waitpid() for child %d failed."%pid)
		self.kill_test = None
		self.test_list_remove()
		
		logf.write("Log complete: %s\n"%relative)
		logf.close()
		rtime = time.time() - self.test_start_time
		stats.completed += 1
		print("Thread complete %s (running time %d)"%(relative, rtime))
		
		# Make the summary page
		os.spawnl(os.P_WAIT, MKDATASUMMARY_PATH, "mkdatasummary.py", LOGBASE_FILE)
	
	# Called by the socket server once the
	# control connection is established.
	# 
	# We are running in our own thread here.
	def handle(self):
		xargs=[]
		try:
			stats.requests += 1
			handshake = False
			line = self.rfile.readline()
			while line != "":
				cmd = line.split()
				if len(cmd) < 1:
					continue
				
				if not handshake:
					self.do_handshake(cmd)
					handshake = True
				else:
					if cmd[0] == "test_source" or \
						cmd[0] == "test_sink":
						self.do_source_sink(cmd)
					elif cmd[0] == "test_pathdiag":
						self.do_pathdiag(cmd, xargs=xargs)
						break  # XXX declare done to force the control connection to close
					elif cmd[0] == "extra_args":
						print ("Client requsted: %s"%line)
						for a in  cmd[1:]:
							for m in validargs:
								if re.match(m, a):
									xargs.append(a)
									break
							else:
								self.wfile.write("extra_args FAILED\n")
								raise ControlProtocolError("Unknown argument: %s"%a)
						self.wfile.write("extra_args OK\n")
					elif cmd[0] == "test_stats":
						self.wfile.write("info stats: " + stats.show())
						self.wfile.write("report none\n")
					else:
						raise ControlProtocolError("Unknown command: %s"%cmd[0])
				line = self.rfile.readline()
		except ControlProtocolError, e:
			print("%s: Control channel error: %s"%(str(self.client_address), str(e)))
		self.finish()

class DiagServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	allow_reuse_address = True
	address_family = socket.AF_INET6
	try:
		socket.socket(address_family, socket.SOCK_STREAM, 0).close() # stupid
	except:
		address_family = socket.AF_INET
	test_list = []
	test_list_cv = threading.Condition()


# Kill off misbehaving tests
def watchdog(serv):
	while True:
		time.sleep(WATCHDOG_TIME/5)
		serv.test_list_cv.acquire()
		try:
			if len(serv.test_list) > 0:
				test = serv.test_list[0]
				if test.kill_test !=  None and time.time() - test.test_start_time > WATCHDOG_TIME:
					print("*** Watchdog expired")
					try:
						test.kill_test(*test.kill_test_args)
					except:
						print("*** Watchdog: warning - got exception while trying to kill")
		except:
			print("*** Watchdog: warning - unhandled exception")
		serv.test_list_cv.release()

# Simple web server
def web_serv():
	print("Web server starting on port %d, directory %s"%(WWW_PORT, WWW_DIR))
	try:
		os.chdir(WWW_DIR)
		HTTPServer((CONTROL_ADDR, WWW_PORT), SimpleHTTPRequestHandler).serve_forever()
	except Exception, e:
		print("Web server died: %s"%e)

def main():
	parser = optparse.OptionParser()
	parser.add_option("-d", action="store_true", dest="detach", \
	                  help="Background daemon")
	parser.add_option("-p", type="string", dest="pidfile", \
	                  default="/var/run/npad.pid", help="Deamon PID file")
	parser.add_option("-u", type="string", dest="user", \
	                  help="Daemon username")
	parser.add_option("-l", type="string", dest="logfilename", \
	                  help="Log file name", default="diag_server_log")
	(opts, args) = parser.parse_args()
	if len(args) != 0:
		parser.error("Unrecognized argument")
	
	if opts.detach:
		if os.fork() != 0:
			os._exit(0)
		os.setsid()
		if os.fork() != 0:
			os._exit(0)
		
		# Write out the pid file.
		f = open(opts.pidfile, "w")
		f.write("%d\n"%os.getpid())
		f.close()
		
		#Become the less priveleged user
		if opts.user != None:
			os.setuid(pwd.getpwnam(opts.user)[2])
		
		# Get rid of stdin/out
		if opts.logfilename[0] != '/':
			opts.logfilename = "%s/%s"%(LOGBASE_FILE, opts.logfilename)
		logfile = os.open(opts.logfilename, os.O_RDWR|os.O_CREAT|os.O_TRUNC)
		devnull = os.open("/dev/null", os.O_RDWR)
		os.dup2(devnull, 0)
		os.dup2(logfile, 1)
		os.dup2(logfile, 2)
		os.close(logfile)
		os.close(devnull)
		
	# Start web server if we have the config
	if have_www_config:
		thread.start_new_thread(web_serv, ())
	
	# Start the diag server
#	serv = DiagServer((CONTROL_ADDR, CONTROL_PORT), DiagRequestHandler)
	serv = DiagServer(('', CONTROL_PORT), DiagRequestHandler) # XXX CONTROL_ADDR not used for dual protocols
	thread.start_new_thread(watchdog, (serv,))
	try:
		serv.serve_forever()
	except KeyboardInterrupt:
		# This waits for threads to complete, at least on some platforms.
		print("Exiting...")
		sys.exit(0)


if __name__ == "__main__": main()
