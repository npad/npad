import os
import socket
import SocketServer
import time
import thread
import random
import select

from Traffic import *

def gen_buf(size=1024*1024):
#	return ''.join(['%c'%random.randint(0, 255) for n in xrange(size)])
	return ''.join(['\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0' for n in xrange(size / 16 + 1)])

class TrafficSock:
	def __init__(self, sock=None, buf=None):
		if sock == None:
			try:
				self.sock = socket.socket(socket.AF_INET6)
			except:
				self.sock = socket.socket(socket.AF_INET)
		else:
			self.sock = sock
		if buf == None:
			self.buf = gen_buf(1024*1024)
		else:
			self.buf = buf
		self.rcvsize = 1024*1024
		self.sink_active = False
		self.source_active = False
	
	def active_open(self, addr):
		self.sock.connect(addr)
	
	def passive_open(self, rmt_host=None):
		self.sock.listen(1)
		while True:
			(newsock, newaddr) = self.sock.accept()
			if rmt_host == None or newaddr[0] == rmt_host:
				break
			newsock.close()
		self.sock.close()
		self.sock = newsock
	
	def sink(self, maxbytes=None, maxtime=None):
		self.sink_active = True
		bytes = 0
		start_time = time.time()
		while (maxbytes == None or bytes < maxbytes) and \
		      (maxtime == None or time.time() - start_time < maxtime):
			n = self.rcvsize
			if maxbytes != None:
				n = min(n, maxbytes - bytes)
			n = len(self.sock.recv(n, socket.MSG_WAITALL))
			bytes += n
			if n == 0:
				break
		self.sink_active = False
	
	def source(self, maxbytes=None, maxtime=None):
		self.source_active = True
		bytes = 0
		start_time = time.time()
		while (maxbytes == None or bytes < maxbytes) and \
		      (maxtime == None or time.time() - start_time < maxtime):
			n = len(self.buf)
			if maxbytes != None:
				n = min(n, maxbytes - bytes)
			bytes += self.sock.send(self.buf[:n])
		self.source_active = False


class TrafficServerSock:
	def __init__(self, laddr, buf=None, sink=True, source=False, \
		     spawn=True, ns_cb=None):
		self.laddr = laddr
		self.buf = buf
		self.sink = sink
		self.source = source
		self.spawn = spawn
		self.ns_cb = ns_cb
		
		self.done = False
	
	def sink_close(self, ts):
		ts.sink()
		if not (ts.sink_active or ts.souce_active):
			ts.sock.close()
	
	def source_close(self, ts):
		ts.source()
		if not (ts.sink_active or ts.source_active):
			ts.sock.close()
	
	def serve(self):
		self.lsock = socket.socket()
		self.lsock.bind(self.laddr)
		self.lsock.listen(5)
		
		while not self.done:
			(sock, addr) = self.lsock.accept()
			if self.ns_cb != None:
				self.ns_cb(sock, addr)
			ts = TrafficSock(sock, self.buf)
			if self.spawn:
				if self.sink:
					thread.start_new_thread(self.sink_close, (ts,))
				if self.source:
					thread.start_new_thread(self.source_close, (ts,))
			else:
				if self.sink:
					self.sink_close(ts)
				if self.source:
					self.source_close(ts)
	
	def stop(self):
		self.done = True
