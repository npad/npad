#!/usr/bin/env python

import sys
import os
import re
import xml.dom.minidom
from optparse import OptionParser

srcpath = os.path.abspath(sys.path[0])
INSTALL_BASE = os.path.normpath(srcpath + "/../npad-dist")
CONFIG_FILENAME = srcpath + "/config.xml"
DIAG_SERVER_CONFIG_FILENAME = srcpath + "/diag_server/DiagServerConfig.py"
WELCOME_IN = srcpath + "/template_diag_form.html"
WELCOME_OUT = srcpath + "/diag_form.html"
VERSION_FILE = srcpath + "/VERSION"
MAKEFILE_INCLUDE = "Makefile.config"
INIT_FILE = srcpath + "/npad"


default_config_str = '''\
<?xml version="1.0" ?>
<config>
	<section name="install">
		<conf key="exec" value="''' + INSTALL_BASE + '''">
			<prompt>Exec dir</prompt>
			<help>The directory to install the diagnostic server,
including binaries, libraries, and configuration files.
It is recommended to use the default value.</help>
		</conf>
		<conf key="www" value="''' + INSTALL_BASE + '''/www">
			<prompt>Web dir</prompt>
			<help>The directory to install web pieces, such as the tester
page and the Java and C clients.  If you are running the
built-in web server (recommended), the default value
should work.  Otherwise you will need to point to a
directory accessible by your web server.</help>
		</conf>
		<conf key="user" value="npad">
			<prompt>User</prompt>
			<help>The user as which the server will run.  We recommend using
a relatively unprivileged user.  If you specify a user
that doesn't exist, 'make install' will create it.</help>
		</conf>
		<conf key="group" value="npad">
			<prompt>Group</prompt>
			<help>The group as which the server will run. We recommend using
a relatively unprivileged group.  If you specify a group
that doesn't exist, 'make install' will create it.</help>
		</conf>
		<conf key="logbase_path" noValOK="yes" level="1">
			<prompt>Log base path</prompt>
		</conf>
		<conf key="logbase_uri" noValOK="yes" level="1">
			<prompt>Log base URI</prompt>
		</conf>
		<conf key="logdir" value="ServerData" level="1">
			<prompt>Server log data directory name</prompt>
		</conf>
	</section>

	<section name="network">
		<conf key="bindAddr" noValOK="yes" level="1">
			<prompt>Bind address</prompt>
			<help>The address to use for binding listen sockets, used if you
need to listen on only one interface on a multi-homed
server.  Entering no value will result in binding to
all addresses, which is appropriate for most servers.</help>
		</conf>
		<conf key="controlPort" value="8001" type="int">
			<prompt>Control port</prompt>
			<help>The port that the control channel listens on.  It should be
safe to leave this alone unless you must work within
firewall restrictions, or unless another service is
using this port.</help>
		</conf>
		<conf key="testPortRangeMin" value="8002" type="int">
			<prompt>Port range min</prompt>
			<help>The bottom of the ephemeral port range used for test
connections.</help>
		</conf>
		<conf key="testPortRangeMax" value="8020" type="int">
			<prompt>Port range max</prompt>
			<help>The top of the ephemeral port range used for test
connections.</help>
		</conf>
		<conf key="threads" value="1" type="int" level="1">
			<prompt>Number of diagnostic threads</prompt>
			<help>Number of cuncurrent pathdiag tests.</help>
		</conf>
		<conf key="defaultRTT" value="20" type="int" level="1">
			<prompt>Default RTT for the JAVA applet.</prompt>
			<help>Provides a hint for the users.</help>
		</conf>
		<conf key="defaultRate" value="100" type="int" level="1">
			<prompt>Default data rate for the JAVA applet.</prompt>
			<help>Provides a hint for the users.</help>
		</conf>
	</section>

	<section name="web_server">
		<conf key="enable" value="yes" type="bool">
			<prompt>Use built-in web server</prompt>
			<help>This package comes with a small python-based web server.
If you would like to use the server, enter "yes".
Otherwise you will need to have installed and set
up another web server such as Apache.</help>
		</conf>
		<conf key="webPort" dep="enable" value="8000" type="int">
			<prompt>Built-in web server port</prompt>
			<help>The port number used by the built-in web server</help>
		</conf>
	</section>

	<section name="pathdiag">
		<conf key="path" noValOK="yes" level="1">
			<prompt>Pathdiag executable path</prompt>
		</conf>
	</section>

	<section name="sourcesink">
		<conf key="maxTime" value="60" level="1">
			<prompt>Max source/sink time</prompt>
		</conf>
	</section>

	<section name="watchdog">
		<conf key="timeout" value="360" level="1">
			<prompt>Watchdog timeout</prompt>
		</conf>
	</section>

	<section name="site">
		<conf key="name">
			<prompt>Site (organization) name</prompt>
			<help>This name should should complete \"NPAD server located at ...\", and
will be used as the title for your server, as it appears on the
tester page.  You must supply a value.</help>
		</conf>
		<conf key="location">
			<prompt>Site location</prompt>
			<help>The geographical location of your server, probably a city name.
Since pathdiag works best over short distances, this information
will be included on the tester page so users can tell how close
they are to the server.  You must supply a value.</help>
		</conf>
		<conf key="position" value="in">
			<prompt>Relative position (in, at, near, etc)</prompt>
			<help>The gramatically correct word that connects the site and location.
			</help>
		</conf>
		<conf key="contactName" noValOK="yes">
			<prompt>Site contact name</prompt>
			<help>The (optional) name of the contact for your site.
This is probably you or the network support team.</help>
		</conf>
		<conf key="contactEmail" noValOK="yes">
			<prompt>Site contact email</prompt>
			<help>This is the (optional) email address for your site contact.</help>
		</conf>
	</section>

	<section name="system">
		<conf key="web100_prefix" value="/usr/local" level="1">
			<prompt>Web100 install prefix</prompt>
		</conf>
	</section>
</config>
'''

ABOVE_APPLET = \
'''<ul>
	<li>
	  The test results are most accurate over a short network path.
	  If this NPAD server (located at %%location%%)
	  is not near you, look for a closer server from the list of
	  <a href="http://www.psc.edu/networking/projects/pathdiag/#servers">
	    Current NPAD Diagnostic&nbsp;Servers</a>.
	</li>
	<li>
	  Have an end-to-end application performance goal
          (<a href="http://www.psc.edu/networking/projects/pathdiag/#target_rtt">target&nbsp;round-trip&nbsp;time</a>
	  and
          <a href="http://www.psc.edu/networking/projects/pathdiag/#target_rate">target&nbsp;data&nbsp;rate</a>)
	  in mind.  Enter the parameters on the form below and click
	  <strong>Start&nbsp;Test</strong>.
	  Messages will appear in the log window as the test runs, followed by a diagnostic report.
	</li>
	<li>
	  In the diagnostic report, failed tests (in <font style="color:red">red</font>) indicate
	  problems that will prevent the application from meeting the end-to-end performance
	  goal.  For each message, a question-mark link (<a href="%%logdir%%/help.html">[?]</a>) leads to
	  additional detailed information about the results.
	</li>
	<li>
	  Every test is fully logged (including your IP address) and test results are
          <a href="%%logdir%%/summary.html">public</a>.
	 We use the logs and results to further refine the software.
	</li>
      </ul>

      For more information, see the
      <a href="http://www.psc.edu/networking/projects/pathdiag/">
	NPAD Documentation</a>, especially the sections:
      <ul>
	<li>
	  <a href="http://www.psc.edu/networking/projects/pathdiag/#procedure">
	    NPAD Diagnostic Procedure</a> - the full instructions.
	</li>
	<li>
	  <a href="http://www.psc.edu/networking/projects/pathdiag/#theory">
	    Theory and Method</a> - why the the tests work.
	</li>
	<li>
	  <a href="http://www.psc.edu/networking/projects/pathdiag/#outcomes">
	    Outcomes</a> - what to do next in the broader debugging context.
	</li>
      </ul>
      <p>

	      <!--
		To get a "border" effect, use a table slightly
		larger than the applet window.  Set it to some
		background color that looks nice.  The applet
		window will be placed over the slightly larger
		table, making a thin border around the applet
		window.
		-->
<p>
'''

TESTER_APPLET = \
'''<applet
     alt="Java is not loading: See the C version below."
     code="DiagClient.class"
     archive="DiagClient.jar"
     width="600" height="300">
     <param name="ControlPort" value="%%control_port%%">
     <param name="DefaultRate" value="%%default_rate%%">
     <param name="DefaultRTT" value="%%default_RTT%%">
   </applet>
'''

C_CLIENT = \
'''<p>If the Java applet above exhibits errors or
      the form is blank, try the command line
      diagnostic client.  Download it
	(<a href="diag-client.c">diag-client.c</a>)
	and compile it:</p>

      <blockquote><pre><strong>
cc diag-client.c -o diag-client
	  </strong></pre></blockquote>

      <p>Run it:</p>

      <blockquote><pre><strong>
./diag-client&nbsp;&lt;server_name&gt;&nbsp;&lt;port&gt;&nbsp;&lt;target_RTT&gt;&nbsp;&lt;target_data_rate&gt;
	  </strong></pre></blockquote>

      <p>Where <em>server_name</em> is the hostname of
      a diagnostic server (e.g., this server), and
      <em>port</em> is the port number the diagnostic
      service runs on (%%control_port%% for this server).
      </p>

'''

ABOUT_NPAD = \
'''<p>This software (NPAD/pathdiag version %%ver%%) is being developed under a 
<a href="http://www.ucar.edu/npad/">collaboration</a>
between the Pittsburgh&nbsp;Supercomputer&nbsp;Center (PSC)
and the National&nbsp;Center for Atmospheric&nbsp;Research (NCAR),
funded under NSF grant ANI-0334061.  The project is focused on using
<a href="http://www.web100.org">Web100</a> and other methods to extend
fairly standard diagnostic techniques to compensate for
"symptom&nbsp;scaling" that leads to false positive diagnostic results
on short paths.  It is still experimental software and may have bugs.
Please help us improve this service by providing feedback about the
results.  Send suggestions, comments and questions to <a
href="mailto:nettune@psc.edu">nettune@psc.edu</a>.</p>

<p>Matt&nbsp;Mathis and John&nbsp;Heffner,
Pittsburgh&nbsp;Supercomputing&nbsp;Center, 2005.</p>
'''

INIT_FILE_TEXT = \
'''#!/bin/sh

# This file is auto-generated by config.py in the NPAD server distribution.
# It is a general init script for starting the NPAD server daemon.  It does
# not use distribution-specific init functions.  You may want to customize
# this if they are important to you.

DIAG_SERVER_DAEMON=%s
USER=%s
PIDFILE=/var/run/npad.pid
DIAG_SERVER_OPTS="-d -u $USER -p $PIDFILE"

start() {
	if [ -f $PIDFILE ]; then
		pid=`cat $PIDFILE`
		if [ "`ps -p $pid -o comm=`" = "python" ]; then
			echo "NPAD server already running, not starting."
			exit 1
		fi
	fi
	${DIAG_SERVER_DAEMON} ${DIAG_SERVER_OPTS}
	echo "NPAD server started."
}

stop() {
	if [ -f $PIDFILE ]; then
		pid=`cat $PIDFILE`
		if [ "`ps -p $pid -o comm=`" = "python" ]; then
			kill $pid
			rm $PIDFILE
			exit 0
		fi
	fi
	exit 1
}

case "$1" in
	start)
		start
		;;
	stop)
		stop
		;;
	restart)
		start
		stop
		;;
	*)
		echo "Usage: $0 {start|stop|restart}"
		exit 1
		;;
esac

exit 0

'''

def getText(nodelist):
	s = ''
	for node in nodelist:
		if node.nodeType == node.TEXT_NODE:
			s = s + node.data
		else:
			if node.hasChildNodes():
				s = s + getText(node.childNodes)
	return s


def getConf(config, section_name, conf_key):
	section = None
	for sec in config.getElementsByTagName("section"):
		if sec.getAttribute("name") == section_name:
			section = sec
			break
	if section == None:
		return None

	for conf in section.getElementsByTagName("conf"):
		if conf.getAttribute("key") == conf_key:
			return conf

	return None

firstPromptVal = True
def promptVal(help_str, prompt_str, noValOK, type=None):
	global firstPromptVal
	if firstPromptVal:
		print("""
---------------------------------------------------------------
| For each configuration value, you will see brief help       |
| followed by a prompt. Default values are in brackets on     |
| the prompt line.  To accept default values, press Enter.    |
---------------------------------------------------------------
""")
		firstPromptVal = False
	if help_str != None:
		print("\n\n%s\n"%help_str)
	val = None
	while val == None:
		s = raw_input(prompt_str)
		if s == "":
			if noValOK:
				return s
			else:
				continue
		if type == "int":
			try:
				int(s)
				val = s
			except:
				print("Must be integer value")
		elif type == "bool":
			if s.lower() == "yes" or s.lower() == "y":
				val = "yes"
			elif s.lower() == "no" or s.lower() == "n":
				val = "no"
			else:
				print('Please enter "yes" or "no"')
		else:
			val = s
	return val

def absPath(path):
	if path[0] != '/':
		path = os.path.normpath(srcpath + '/' + path)
	return path


def main():
	#
	# Parse command line options
	#
	parser = OptionParser()
	parser.add_option("-p", action="store_true", dest="prompt", \
	                  help="Prompt for options even if already configured")
	parser.add_option("-a", action="store_true", dest="advanced", \
	                  help="Prompt for advanced configuration options")
	(opts, args) = parser.parse_args()
	if len(args) != 0:
		parser.error("Unrecognized argument")

	#
	# Parse the default config (above)
	#
	def_doc = xml.dom.minidom.parseString(default_config_str)
	def_config = def_doc.getElementsByTagName("config")[0]

	#
	# Load and parse the old config if it exists
	#
	try:
		old_doc = xml.dom.minidom.parse(CONFIG_FILENAME)
		old_config = old_doc.getElementsByTagName("config")[0]
		old_sections = old_doc.getElementsByTagName("section")
		print("\nImporting existing config.xml.")
	except IOError:
		old_doc = None
		old_config = None
		old_sections = None

	#
	# Create the new config
	#
	doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "config", None)
	config = doc.getElementsByTagName("config")[0]
	config.appendChild(doc.createComment("""
This file is auto-generated by config.py in the NPAD Diagnostic Server
distribution.  Hand-editing is not recommended.  Re-run config.py with
the '-p' flag to change values.
"""))

	#
	# Merge old and default configs, prompt as necessary
	#
	for def_section in def_config.getElementsByTagName("section"):
		section_name = def_section.getAttribute("name")

		old_section = None
		if old_sections != None:
			for olds in old_sections:
				if olds.getAttribute("name") == section_name:
					old_section = olds
					break

		section = doc.createElement("section")
		section.setAttribute("name", section_name)

		for def_conf in def_section.getElementsByTagName("conf"):
			key = def_conf.getAttribute("key")

			conf = doc.createElement("conf")
			conf.setAttribute("key", key)

			default_value = None
			old_conf = None
			if old_section != None:
				for oc in old_section.getElementsByTagName("conf"):
					if oc.getAttribute("key") == key:
						old_conf = oc
						if oc.hasAttribute("value"):
							default_value = oc.getAttribute("value")
						break
			if old_conf == None:
				if def_conf.hasAttribute("value"):
					default_value = def_conf.getAttribute("value")

			value = default_value
			if (old_conf == None or opts.prompt) and \
			   (not def_conf.hasAttribute("level") or opts.advanced):
				helpElems = def_conf.getElementsByTagName("help")
				help_str = None
				if len(helpElems) > 0:
					help_str = getText(helpElems)
				prompt_str = getText(def_conf.getElementsByTagName("prompt"))
				if default_value != None:
					prompt_str = prompt_str + " [%s]"%default_value
				prompt_str = prompt_str + ": "

				s = promptVal(help_str, prompt_str, \
				                  default_value != None or def_conf.getAttribute("noValOK") == "yes", \
				                  def_conf.getAttribute("type"))
				if s != "":
					value = s

			if value != None:
				conf.setAttribute("value", value)

			section.appendChild(conf)

		config.appendChild(section)

	#
	# Write out the new config file.
	#
	config_file = open(CONFIG_FILENAME, "w")
	config_file.write(doc.toprettyxml())
	config_file.close()

	#
	# Look for Web100 library
	#
	wc_prefix = absPath(getConf(config, "system", "web100_prefix").getAttribute("value"))
	wc_path = absPath("%s/lib/python%s/site-packages"%(wc_prefix, sys.version[:3]))
	if not wc_path in sys.path:
		sys.path.append(wc_path)
	try:
		import Web100
	except:
		print("""*** WARNING ***  Web100 library not found at %s.
Make sure you have the latest Web100 userland package installed.
If it is installed in a non-standard location, re-run config.py
with the -a switch and specify your install prefix when prompted
for it."""%wc_path)

	#
	# Get absolute paths
	#
	exec_path = absPath(getConf(config, "install", "exec").getAttribute("value"))
	www_path = absPath(getConf(config, "install", "www").getAttribute("value"))

	conf = getConf(config, "install", "logbase_path")
	if conf.hasAttribute("value"):
		logdir_path = absPath(conf.getAttribute("value"))
	else:
		logdir_path = www_path
	logdir_path = logdir_path + "/" + getConf(config, "install", "logdir").getAttribute("value")

	conf = getConf(config, "pathdiag", "path")
	if conf.hasAttribute("value"):
		pathdiag_path = conf.getAttribute("value")
	else:
		pathdiag_path = exec_path


	#
	# Create DiagServerConfig.py
	#
	dsc_file = open(DIAG_SERVER_CONFIG_FILENAME, "w")
	dsc_file.write("""#
# This file is auto-generated by config.py in the NPAD Diagnostic Server
# distribution.  Hand-editing is not recommended.  Re-run config.py with
# the '-p' flag to change values.
#

""")

	dsc_file.write('LOGBASE_URL = "' + \
	               getConf(config, "install", "logbase_uri").getAttribute("value") + \
	               getConf(config, "install", "logdir").getAttribute("value") + '"\n')

	dsc_file.write('LOGBASE_FILE = "%s"\n'%logdir_path)

	dsc_file.write('CONTROL_ADDR = "' + \
	               getConf(config, "network", "bindAddr").getAttribute("value") + '"\n')
	dsc_file.write('CONTROL_PORT = ' + \
	               getConf(config, "network", "controlPort").getAttribute("value") + '\n')
	dsc_file.write('TEST_PORTRANGE_MIN = ' + \
	               getConf(config, "network", "testPortRangeMin").getAttribute("value") + '\n')
	dsc_file.write('TEST_PORTRANGE_MAX = ' + \
	               getConf(config, "network", "testPortRangeMax").getAttribute("value") + '\n')
	dsc_file.write('THREADS = ' + \
	               getConf(config, "network", "threads").getAttribute("value") + '\n')

	dsc_file.write('PATHDIAG_PATH = "%s"\n'%(pathdiag_path+"/pathdiag.py"))
	dsc_file.write('MKDATASUMMARY_PATH = "%s"\n'%(pathdiag_path+"/mkdatasummary.py"))

	dsc_file.write('MAX_SOURCESINK_TIME = ' + \
	               getConf(config, "sourcesink", "maxTime").getAttribute("value") + '\n')
	dsc_file.write('WATCHDOG_TIME = ' + \
	               getConf(config, "watchdog", "timeout").getAttribute("value") + '\n')
	dsc_file.write('WC_PATH = "%s"\n'%wc_path)

	# XXX pS needs to know WWW_* even if we are not running our own server
	if getConf(config, "web_server", "enable").getAttribute("value") == "yes":
		dsc_file.write('WWW_DIR = "%s"\n'%getConf(config, "install", "www").getAttribute("value"))
		dsc_file.write('WWW_PORT = %s\n'%getConf(config, "web_server", "webPort").getAttribute("value"))

	dsc_file.close()


	#
	# Create tester page
	#
	site_str = getConf(config, "site", "name").getAttribute("value")
	location_str = getConf(config, "site", "location").getAttribute("value")

	ver_file = open(VERSION_FILE, "r")
	version_str = ver_file.readline().strip()
	ver_file.close()

	name_str = getConf(config, "site", "contactName").getAttribute("value")
	email_str = getConf(config, "site", "contactEmail").getAttribute("value")
	if name_str != "" or email_str != "":
		site_contact_str = "<p>Please send comments and suggestions about the server to "
		if email_str != "":
			site_contact_str = site_contact_str + '<a href="mailto:%s">'%email_str
			if name_str != "":
				site_contact_str = site_contact_str + '%s &lt;%s&gt;'%(name_str, email_str)
			else:
				site_contact_str = site_contact_str + '%s'%email_str
			site_contact_str = site_contact_str + '</a>'
		else:
			site_contact_str = site_contact_str + name_str
		site_contact_str = site_contact_str + ".</p>"
	else:
		site_contact_str = ""

	logdir_str = getConf(config, "install", "logdir").getAttribute("value")
	port_str = getConf(config, "network", "controlPort").getAttribute("value")
	default_rate = getConf(config, "network", "defaultRate").getAttribute("value")
	default_RTT = getConf(config, "network", "defaultRTT").getAttribute("value")

	welcome_in = open(WELCOME_IN, "r")
	welcome_str = welcome_in.read()
	welcome_in.close()

	for (in_s, out_s) in (
		# blocks of text first
		("%%above_applet%%", ABOVE_APPLET),
		("%%tester_applet%%", TESTER_APPLET),
		("%%c_client%%", C_CLIENT),
		("%%about_npad%%", ABOUT_NPAD),
		# followed by keyword substution
		("%%site%%", site_str),
		("%%location%%", location_str),
		("%%ver%%", version_str),
		("%%site_contact%%", site_contact_str),
		("%%logdir%%", logdir_str),
		("%%control_port%%", port_str),
		("%%default_rate%%", default_rate),
		("%%default_RTT%%", default_RTT) ):
		welcome_str = re.sub(in_s, out_s, welcome_str)

	welcome_out = open(WELCOME_OUT, "w")
	welcome_out.write(welcome_str)
	welcome_out.close()


	server_user = getConf(config, "install", "user").getAttribute("value")
	server_group = getConf(config, "install", "group").getAttribute("value")

	#
	# Write out Makefile include
	#
	include_file = open(MAKEFILE_INCLUDE, "w")
	include_file.write("EXEC_DIR = %s\n"%exec_path)
	include_file.write("WWW_DIR = %s\n"%www_path)
	include_file.write("LOGDIR = %s\n"%logdir_path)
	include_file.write("USER = %s\n"%server_user)
	include_file.write("GROUP = %s\n"%server_group)
	include_file.write("WC_PREFIX = %s\n"%wc_prefix)
	include_file.close()

	#
	# Write out Sys V init script
	#
	init_file = open(INIT_FILE, "w")
	init_file.write(INIT_FILE_TEXT%(exec_path+"/DiagServer.py", server_user))
	init_file.close()
	os.chmod(INIT_FILE, 0755)

	print("\nConfiguration complete.  You're now ready to 'make'.\n")


if __name__ == "__main__": main()
