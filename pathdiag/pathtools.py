import sys
import time
import socket
from types import LongType, FloatType
import libweb100
import Web100 as PyWeb100
from pathlib import *

################################################################
# report generation
# stdout and/or a .txt file

stdouttype="T"
tfile=None
def runlog(lvl, msg):
    "Prepare to deprecate this report generation"
    global tfile, stdouttype, tfmt

    if (not lvl in tfmt["T"]) or (not lvl in tfmt["H"]):
	lvl="X"
    if lvl=="X":
	pass  # XXX exceptional = True

    # fixup the html character encoding
#    hmsg = msg.replace(">","&gt;")
#    if hmsg[1]==" ":
#	hmsg="&nbsp;&nbsp;"+hmsg

    # stdout first
    if stdouttype=="T":
	print tfmt[stdouttype][lvl]%msg,
    else:
	print tfmt[stdouttype][lvl]%hmsg,
    sys.stdout.flush()

    # and then the file
    if tfile:
	tfile.write(tfmt["T"][lvl]%msg)

#def html(str):
#    """ Unformated html output """
#    global stdouttype
#    if stdouttype=="H":
#	print str

tfmt={}
tfmt["T"]={}
tfmt["H"]={}
#	tester information
# X Unknown
# H heading				(Big, black)
# T Tester problem			(yellow)
# I Misc info, progress reports		(grey)
#	Test information
# M mesurments and targets or goals	(black)
# P pass				(green)
# W warn, test may be inaccurate	(orange)
# F fail				(red) 
# N novice - 				(blue)
# WA, FA *Action		(bold, ital)

# X - undfined entropy
tfmt["T"]["X"]="XXX: %s\n"
tfmt["H"]["X"]="XXX: %s<br>\n"
# H Heading					(h1 black)
tfmt["T"]["H"]="%s\n"
tfmt["H"]["H"]="<H1>%s</H1>\n"
# T Tester problem/limitation			(yellow)
tfmt["T"]["T"]="%s\n"
tfmt["H"]["T"]="<font color=\"#C0C000\">%s</font><br>\n"
# E Tester error				(Red)
tfmt["T"]["E"]="%s\n"
tfmt["H"]["E"]="<font color=\"#FF0000\">%s</font><br>\n"
# I Misc info, progress reports			(grey)
tfmt["T"]["I"]="%s\n"
tfmt["H"]["I"]="<font color=\"#C0C0C0\">%s</font><br>\n"
# M Measurement and targets or goals		(black)
tfmt["T"]["M"]="%s\n"
tfmt["H"]["M"]="<font color=\"#000000\">%s</font><br>\n"
# P Pass					(Green)
tfmt["T"]["P"]="%s\n"
tfmt["H"]["P"]="<font color=\"#00FF00\">%s</font><br>\n"
# W Warn, moderate problem with path or tester	(Orange)
tfmt["T"]["W"]="%s\n"
tfmt["H"]["W"]="<font color=\"#FFC000\">%s</font><br>\n"
# WA Warn Action				(BI Orange)
tfmt["T"]["WA"]="%s\n"
tfmt["H"]["WA"]="<font color=\"#FFC000\"><b><i>%s</i></b></font><br>\n"
# F Fail					(Red)
tfmt["T"]["F"]="%s\n"
tfmt["H"]["F"]="<font color=\"#FF0000\">%s</font><br>\n"
# FA FailAction					(BI Red)
tfmt["T"]["FA"]="%s\n"
tfmt["H"]["FA"]="<font color=\"#FF0000\"><b><i>%s</i></b></font><br>\n"
# N Novice - overly helpful			(Blue)
tfmt["T"]["N"]="%s\n"
tfmt["H"]["N"]="<font color=\"#0000FF\">%s</font><br>\n"

def setupRunlog(opts, fmt):
    global tfile, stdouttype
    tfile = None

    fmt=fmt.upper()
    stdouttype=fmt[0]
    if stdouttype != "H":
	stdouttype="T"

    fmt=fmt[1:]
    if "T" in fmt:
	tfile=open(opts.logbase+".txt", "w")
################################################################
# Setup and pre-test

def setupParse(p):
    # Host/connection selection
    p.add_option("-H", "--host",
	help="Host to connect to", 
	type="string", default="", dest="host")
    p.add_option("-C", "--cid",
	help="CID of TCP connection to use",
	type="int", default=-1, dest="cid")
    p.add_option("-F", "--fd",
	help="File descriptor of an open TCP connection (int)",
	type="int", default=-1, dest="fd")
    p.add_option("-x", "--xmit",
	help="Transmit data on specidifed FD (with -F only)",
	action="store_true", default=False, dest="ixmit")
    p.add_option("-L", "--listen",
	help="Listen for an incoming connection",
	action="store_true", default=False, dest="listen_opt")
    p.add_option("-P", "--port",
	help="Port (default is 56117)",
	type="int", default=56117, dest="port")

    # override low level properties
    p.add_option("-B", "--bully",
	help="Stiffen TCP (beyond AIMD)",
	type="int", dest="bully")
    p.add_option("-U", "--mss",
	help="Set MSS (down only)",
	type="int", default=0, dest="set_mss")

    # server only stuff
    p.add_option("", "--queclient",
	type="string", default="")
    p.add_option("", "--maxtime",
	help="Running time limit (5 minute default)",
	type="int", default=300)	# 10 minutes

def queClient(opts):
    """
	Send a message on the "control channel" that we are ready for an active client.

	This is really part of a diagnostic server, but it makes life so much easier.
    """
    if opts.queclient:
	# this has to be a naked print to stdout.  It may be incompatable with --format=h??
	print "%s %d\n"%(opts.queclient, opts.port)
	sys.stdout.flush()

timelimit=0
def setupTCP(opts):
    """
    Setup the TCP connection for a test.
    """

    # Set up the internal soft watchdog
    global maxtime
    maxtime = time.time() + opts.maxtime - 5	# deduct 5 seconds for slop

    # Set up web100 access
    global ag
    ag = libweb100.web100_attach(libweb100.WEB100_AGENT_TYPE_LOCAL, None)
    if ag == None:
        runlog("F","Web100 not initialized/not installed")
        sys.exit(1)
    try:
	cvar.gread = libweb100.web100_group_find(ag,"read")
        cvar.gtune = libweb100.web100_group_find(ag,"tune")
    except Exception, e:
        runlog("F","Web100 setup error %s"%(e))
        sys.exit(1)

    # Find/create the connection to test
    global cid, pid, ixmit, datasock

    cid = -1
    ixmit = opts.ixmit			# -x
    if (opts.host):			# -H Hostname
        for addrinfo in socket.getaddrinfo(opts.host, opts.port, socket.AF_UNSPEC, socket.SOCK_STREAM):
            (af, socktype, proto, canonname, sa) = addrinfo
            try:
                if opts.verbose:
                    gn=socket.getnameinfo(sa, 1)
                    runlog("I", "Trying %s Port %s"%(gn[0], gn[1]))
                datasock = socket.socket(af, socktype, proto)
            except Exception, e:
                runlog("F", "Failed to create socket: %s"%(e))
                sys.exit(2)
            try:
                datasock.connect(sa)
            except Exception, e:
                gn=socket.getnameinfo(sa, 1)
                runlog("F", "Failed to establish connection to %s on port %s, %s"%(gn[0], gn[1], e))
                sys.exit(2)
            try:
                cvar.conn = libweb100.web100_connection_from_socket(ag, datasock.fileno())
            except Exception, e:
                runlog("F", "Failed to get web100 conn %s"%(e))
                sys.exit(2)
            if cvar.conn == 0:
                runlog("F", "Failed to find the connection %s"%(e))
                sys.exit(2)
            try:
                cid = libweb100.web100_get_connection_cid(cvar.conn)
            except Exception, e:
                runlog("F", "Failed to find web100 cid %s"%(e))
                sys.exit(2)
        ixmit = 1
    elif (opts.cid <> -1):		# -C cid
        # cid is already set
        # cid = opts.cid
	if opts.verbose:
	    runlog("I", "Using existing CID %d"%(cid))
        try:
            cvar.conn = libweb100.web100_connection_lookup(ag, cid)
        except Exception, e:
            runlog("F", "Failed to get web100 conn %s"%(e))
            sys.exit(2)
        ixmit = 0
    elif (opts.fd <> -1):		# -F fd
	if opts.verbose:
	        runlog("I", "Using existing file descriptor from parent %d"%(opts.fd))
        try:
            cvar.conn = libweb100.web100_connection_from_socket(ag, opts.fd);
        except Exception, e:
            runlog("F", "Failed to get web100 conn %s"%(e))
            sys.exit(2)
        try:
            cid = libweb100.web100_get_connection_cid(cvar.conn)
        except Exception, e:
            runlog("F", "Failed to get web100 cid %s"%(e))
            sys.exit(2)
        try:
            datasock = socket.fromfd(opts.fd, socket.AF_INET, socket.SOCK_STREAM)
        except Exception, e:
            runlog("F", "Failed to use file descriptor %s passed in from parent process"%(opts.fd))
            sys.exit(2)
        # ixmit from -x option
    elif (opts.listen_opt):		# -L (isten)
	if opts.verbose:
            runlog("I", "Listening for a connection on port %d"%(opts.port))
        try:
            lsock = socket.socket()
        except Exception, e:
            runlog("F", "Couldn't create socket: %s"%(e))
            sys.exit(2)
        try:
            lsock.bind(("", int(opts.port)))
        except Exception, e:
            runlog("F", "Couldn't bind port %d: %s"%(opts.port, e))
            sys.exit(2)
        try:
            lsock.listen(1)
        except Exception, e:
            runlog("F", "Couldn't \"listen\" on port %d: %s"%(opts.port, e))
            sys.exit(2)
        queClient(opts)
        try:
            datasock, addr = lsock.accept()
        except Exception, e:
            runlog("F", "Failed to accept connection on port %d: %s"%(opts.port, e))
            sys.exit(2)
        try:
            cvar.conn = libweb100.web100_connection_from_socket(ag, datasock.fileno())
        except Exception, e:
            runlog("F", "Failed to get web100 conn %s"%(e))
            sys.exit(2)
        try:
            cid = libweb100.web100_get_connection_cid(cvar.conn)
        except Exception, e:
            runlog("F", "Failed to get web100 cid %s"%(e))
            sys.exit(2)
        ixmit = 1
    else:
        runlog("F", "Must specify on of -H, -C, -F or -L on command line")
        sys.exit(2)
    if cid == -1:
        runlog("F", "Failed to establish or locate connection, cid = -1")
	sys.exit(2)
    if ixmit:
        pid = pumpsegs(datasock.fileno(), 1000000)	# XXX - fixed buffer/write size
        # note: pid_t has no distructor, so this is technically a leak.
        # therfore we need -DSWIG_PYTHON_SILENT_MEMLEAK to silence the rt complaint

    # we do no validity checking here - we rely on the kernel
    # Later checks will catch problems
    if opts.set_mss:
	runlog("W", "Set MSS to %d"%(opts.set_mss))
	write_web100_var(cvar.conn, cvar.gtune, "CurMSS", opts.set_mss)
	cvar.baseMSS = opts.set_mss

def pretuneTCP(opts):
    """ Make any pre-test adjustments to TCP. """

    # If bully mode we replace AIMD with our own
    if opts.bully:
        one, ssthresh=1, 2*cvar.baseMSS
        vWADNoAI=libweb100.web100_var_find(cvar.gtune, "WAD_NoAI")
        libweb100.web100_raw_write(vWADNoAI, cvar.conn, one)
	try:
	    vLimSsthresh=libweb100.web100_var_find(cvar.gtune, "LimSsthresh")
	except Exception, e:
            runlog("F", "No LimSsthresh - Check for a newer Web100 kernel!")
	    sys.exit(1)
        libweb100.web100_raw_write(vLimSsthresh, cvar.conn, ssthresh)
        runlog("W", "Set bully mode %d"%(libweb100.web100_raw_read(vLimSsthresh, cvar.conn)))

################################################################
# run_ something
################################################################
allRuns = []   # strictly chronological
rowcount = 0

def init_elapsed_sample(ctl):
    """
    Gather the "zeroth" data sample,
    from the current state of the connection

    All samples (including this one) are archived in cronological order in allRuns.
    """
    global ns, rowcount, allRuns
    ns = libweb100.web100_snapshot_alloc(cvar.gread, cvar.conn)
    libweb100.web100_snap(ns)
    r={}
    r["tctrl"]=ctl
    r["rawsnap"]=ns
    r.update(mkdict(ctl, ns, None))
    r["row"] = rowcount
    rowcount += 1
    allRuns.append(r)
    cvar.baseMSS = r["CurMSS"]

def run_elapsed_sample(ctl):
    """
    Gather a data sample.

    All of the argument specified in ctrl are passed to the c code to actually
    manipulate TCP and collect data, without the overhead of the python interperter.

    All samples are archived in cronological order in allRuns.
    """
    global os, ns, rowcount, allRuns
    os, ns = ns, watch_elapsed_sample(cvar.conn, ctl) # beware: alters ctl
    r={}
    r["tctrl"]=ctl
    r["rawsnap"]=ns
    r.update(mkdict(ctl, ns, os))
    r["row"] = rowcount
    rowcount += 1
    if time.time() > maxtime:
	r["maxtime"]=True
    allRuns.append(r)
    return(r)

################################################################
# Interim dictionary definitions
################################################################
overflow = 4294967296L		# 2^32 to force unconditional unsigned long
mask = overflow-1
def rntohl(a):
    global overflow, mask
    a = (a+overflow) & mask
    if socket.ntohl(1) != 1:	# Snaps are little endian
	return(a)
    r = ((a & 0x0FF) << 24) | \
	((a & 0x0FF00) << 8) | \
	((a & 0x0FF0000) >> 8) | \
	((a >> 24) & 0x0FF)
    return(r)

overflow64=18446744073709551616L
mask64=overflow64-1
def rntohll(a):
    global overflow64, mask64
    a = (a+overflow64) & mask64
    if socket.ntohl(1) != 1:	# Snaps are little endian
	return(a)
    r = ((a & 0x0FFL) << 56) | \
	((a & 0x0FF00L) << 40) | \
	((a & 0x0FF0000L) << 24) | \
	((a & 0x0FF000000L) << 8) | \
	((a & 0x0FF00000000L) >> 8) | \
	((a & 0x0FF0000000000L) >> 24) | \
	((a & 0x0FF000000000000L) >> 40) | \
	((a >> 56) & 0x0FF)
    return(r)

# test rntohll()
def testrntohll():
    i = overflow64
    while i:
	i = i >> 1
	r = rntohll(i)
	print "%x %x"%(i, r)
    sys.exit()
# testrntohll()

def mkdict(ctl, new, old):
    """
    Convert a tctrl and two snaps into a dictionary.   This parallels John Heffners
    new python API for Web100, but handles deltas differently.

    Don't compute deltas, if there is no prior (old) sample.

    """
    r = {}

    # process the control structure
    # eeeewww clearly this is lame XXX
    r["flag"]=ctl.flag
    r["basemss"]=ctl.basemss
    r["win"]=ctl.win
    r["burstwin"]=ctl.burstwin
    r["duration"]=ctl.duration
    r["obswin"]=ctl.obswin
    r["SSbursts"]=ctl.SSbursts
    r["SSbully"]=ctl.SSbully
    r["SSbullyStall"]=ctl.SSbullyStall
    r["SSsumAwnd"]=ctl.SSsumAwnd
    r["SScntAwnd"]=ctl.SScntAwnd
    r["SSpoll"]=ctl.SSpoll

    # Process the snaps
    # This interim version violates clean layering:
    # it uses a hybrid of libweb100 and PyWeb100

    v = libweb100.web100_var_head(cvar.gread)
    while v:
	vv = PyWeb100.Web100Var(v, cvar.gread)   # ugly

        n = libweb100.web100_get_var_name(v)
        t = libweb100.web100_get_var_type(v)
	if libweb100.web100_snap_read(v, new, cvar.nbuf) != libweb100.WEB100_ERR_SUCCESS:
	    raise "snap read fail"
	if old:
	    if libweb100.web100_snap_read(v, old, cvar.obuf) != libweb100.WEB100_ERR_SUCCESS:
		raise "snap read fail"
        if   ( t == libweb100.WEB100_TYPE_COUNTER32 ):
	    r["abs_"+n]=rntohl(vv.val(cvar.nbuf))	# abs_ is absolute magnitude
	    if old:
		delta = rntohl(vv.val(cvar.nbuf)) - rntohl(vv.val(cvar.obuf))
		if delta < 0:
		    delta = delta + 4294967296
		r[n] = delta
        elif   ( t == libweb100.WEB100_TYPE_COUNTER64 ):
	    r["abs_"+n]=rntohll(vv.val(cvar.nbuf))	# abs_ is absolute magnitude
	    if old:
		# rntohl() is wrong
		delta = rntohll(vv.val(cvar.nbuf)) - rntohll(vv.val(cvar.obuf))
		if delta < 0:
		    delta = delta + 18446744073709551616
		r[n] = delta
        elif ( t == libweb100.WEB100_TYPE_GAUGE32 or
	       t == libweb100.WEB100_TYPE_INTEGER32 or
	       t == libweb100.WEB100_TYPE_UNSIGNED32 or
	       t == libweb100.WEB100_TYPE_TIME_TICKS or
	       t == libweb100.WEB100_TYPE_INTEGER ):
	    r[n] = rntohl(vv.val(cvar.nbuf))
        else:
            r[n] = vv.val(cvar.nbuf)
        v = libweb100.web100_var_next(v)
#	vv.free()
    return(r)


################################################################
# File saving and restoring code
################################################################
def write_events(ev, f):
    for e in ev:
	if isinstance(ev[e], int):
	    f.write("%s event_int %d\n"%(e, ev[e]))
	elif isinstance(ev[e], str):
	    f.write("%s event_str %s\n"%(e, ev[e]))
	elif type(ev[e]) == LongType:
	    f.write("%s event_long %Ld\n"%(e, ev[e]))
	elif type(ev[e]) == FloatType:
	    f.write("%s event_float %s\n"%(e, ev[e]))
	else:
	    try:
		row=ev[e]["row"]
		f.write("%s event_row %d\n"%(e, row))
	    except:
		f.write("%s event_other %s\n"%(e, str(ev[e])))

def diff_events(nev, oev, f):
    for e in nev:
	if e in oev:
	    try:
		nrow=nev[e]["row"]
		orow=oev[e]["row"]
		if nrow != orow:
		    f.write("  %s different rows: %d %d\n"%(e, nrow, orow))
	    except:
		if nev[e] != oev[e]:
		    f.write("  %s new: %s\n"%(e, nev[e]))
		    f.write("      old: %s\n"%oev[e])

def write_stats(ev, lbase):
    """
    Write test parameters and results to a pair of files

    Test test parameters and control information (struct tcrtl) is
    written to the ascii file <name>.ctl
    Binary web100 snaps are written to <name>.log
    """
    global allRuns
    fver = "20060411"

    # setup control log and write (almost) all events
    logf = open(lbase + ".ctrl", 'w')
    logf.write("version %s\n"%fver)

    # setup snap log
    vlog = libweb100.web100_log_open_write(lbase + ".log", cvar.conn, cvar.gread)
    
    for r in allRuns:
        c, s = r["tctrl"], r["rawsnap"]
        logf.write("tctrl 20050126 %d %d %d %d %d %d %d %d %d %d %d %d\n"%(
            c.flag, c.basemss, c.win, c.burstwin, c.duration, c.obswin,
            c.SSbursts, c.SSbully, c.SSbullyStall, c.SSsumAwnd, c.SScntAwnd, c.SSpoll))
        libweb100.web100_log_write(vlog, s)

    write_events(ev, logf)
    logf.close()
    libweb100.web100_log_close_write(vlog)

def old_write_stats(lbase, plist):
    """
    Write test parameters and results to a pair of files

    Test test parameters and control information (struct tcrtl) is
    written to the ascii file <name>.ctl
    Binary web100 snaps are written to <name>.log
    """

    # setup control log and write test parameters
    logf = open(lbase + ".ctrl", 'w')
    for p in plist:
	logf.write("%d "%p)
    logf.write("\n")

    # setup snap log
    vlog = libweb100.web100_log_open_write(lbase + ".log", cvar.conn, cvar.gread)
    
    for r in allRuns:
        c, s = r["tctrl"], r["rawsnap"]
        logf.write("10 20050126 : %d %d %d %d %d %d %d %d %d %d %d %d\n"%(
            c.flag, c.basemss, c.win, c.burstwin, c.duration, c.obswin,
            c.SSbursts, c.SSbully, c.SSbullyStall, c.SSsumAwnd, c.SScntAwnd, c.SSpoll))
        libweb100.web100_log_write(vlog, s)

    logf.close()
    libweb100.web100_log_close_write(vlog)

def read_stats(lbase):
    """
    Read previously saved test results written by write_stats
    """
    global ag, allRuns

# Open the logs with the appropriate tools 
    logf =  open(lbase + ".ctrl", 'r')
    vlog = libweb100.web100_log_open_read(lbase + ".log")
    ag = libweb100.web100_get_log_agent(vlog)
    cvar.gread  = libweb100.web100_get_log_group(vlog)
    cvar.conn = libweb100.web100_get_log_connection(vlog)

# parse test prameters (first line)
    firstline = logf.readline().split(' ')

    # old format always started with a digit
    if firstline[0].isdigit():
	return(old_read_stats(firstline, logf, vlog))

    if firstline[0] != "version":
	raise "malformed ctrl file version"
    fver = firstline[1]
    ev,ar={},[]
    # new format is keyword driven
    for line in logf.readlines():
	w=line.split()
	name = w[0]
	if w[1] == "event_str":
	    ev[name] = " ".join(w[2:])
	elif w[1] == "event_int":
	    ev[name] = int(w[2])
	elif w[1] == "event_long":
	    ev[name] = long(w[2])
	elif w[1] == "event_float":
	    ev[name] = float(w[2])
	elif w[1] == "event_row":
	    ev[name] = ar[int(w[2])]
	elif w[1] == "event_other":
	    ev[name] = None	# XXX - not supported
	elif w[1] == "20050126":
	    c=parse_tctrl_20050126(2, w)
	    s = libweb100.web100_snapshot_alloc( cvar.gread, cvar.conn )
	    libweb100.web100_snap_from_log(s, vlog)
	    d={}
	    d["tctrl"]=c
	    d["rawsnap"]=s
	    ar.append( d )
	else:
	    raise "unknown .ctrl line: "+w[1]
    allRuns=ar
    return ev,ar
	
def parse_tctrl_20050126(i, w):
    c = tctrl()
    i, c.flag = i+1, int(w[i])
    i, c.basemss = i+1, int(w[i])
    i, c.win = i+1, int(w[i])
    i, c.burstwin = i+1, int(w[i])
    i, c.duration = i+1, int(w[i])
    i, c.obswin = i+1, int(w[i])
    i, c.SSbursts = i+1, int(w[i])
    i, c.SSbully = i+1, int(w[i])
    i, c.SSbullyStall = i+1, int(w[i])
    i, c.SSsumAwnd = i+1, int(w[i])
    i, c.SScntAwnd = i+1, int(w[i])
    i, c.SSpoll = i+1, int(w[i])
    if (i != len(w)):
	raise "missaligned format error"
    return(c)	    

def old_read_stats(firstline, logf, vlog):
    """
    Read old logfiles,
    note that this is not verbatum old code
    """
    global allRuns
    ev,rr={},[] # return result (deprecated)
    for w in firstline:
	if w.isdigit():
	    rr.append(int(w))
    ev["target_rate"] = rr[0]
    ev["target_rtt"] = rr[1]

# parse control parameters and web100 snaps in tandom for individual tests
    ar = [] # scan result
    for l in logf:
        w=l.split(' ')
        if w[0:3] == [ "10", "20050126", ":" ] and len(w) == 15:
	    c = parse_tctrl_20050126(3, w)
        elif w[0:3] == [ "10", "20040330", ":" ] and len(w) == 13:
	    raise "deprecate this format"	# XXX nuke (all of) this
            c = tctrl()
            i=3
            i, c.flag = i+1, int(w[i])
            i, c.basemss = i+1, int(w[i])
            i, c.win = i+1, int(w[i])
            i, c.burstwin = i+1, int(w[i])
            i, c.duration = i+1, int(w[i])
            i, c.obswin = i+1, int(w[i])
            i, c.SSbursts = i+1, int(w[i])
            i, c.SSbully = i+1, int(w[i])
            i, c.SSsumAwnd = i+1, int(w[i])
            i, c.SScntAwnd = i+1, int(w[i])
            i, c.SSpoll = i+1, -1 
            i, c.SSbullyStall = i+1, -1 # reordered
	    if (i != SizeOfTctrl):
		raise "missaligned format error"
	else:
	    print len(w), w
            raise "format error"
        s = libweb100.web100_snapshot_alloc( cvar.gread, cvar.conn )
        libweb100.web100_snap_from_log(s, vlog)
	d={}
	d["tctrl"]=c
	d["rawsnap"]=s
        ar.append( d )
    allRuns=ar
    return ev,ar

