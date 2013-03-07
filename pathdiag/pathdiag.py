#!/usr/bin/env python

"""
A path diagnostic.

See: http://www.psc.edu/networking/projects/pathdiag/

The algorithm is based on 
"""
import sys
import socket
import math
from optparse import OptionParser
import string
import pathtools as pp
import prettyhtml as ph
plotok=True
try:
    import Gnuplot
except ImportError:
    plotok=False

from types import *
from pathlib import *

version="$Id: pathdiag.py,v 1.47 2009/06/10 21:19:57 mathis Exp $"

################################################################
# Various useful math
################################################################
def div(n, d, e=99999):
    """ A safe division, with a default that is taken for divide by zero """
    if d:
        return(n/d)
    else:
        return(e)

def fitSqrt(rtt, time, pkts, loss):
    """
	Returns 1.0 or greater if we are doing as well as AIMD.

	Actually returns an estimate for "C" in the AIMD model.
	If return >> 1.0, then bully mode is being abusive
	Note: rtt in ms, time in us.
    """
    try:
	return(1000.0*rtt/time*math.sqrt(pkts*loss))
    except:
	return(0.0)

def setTarget_runlen(ev, mss):
    """
    Set target_runlen from the target_rate, target_rtt and the mss.

    Note that mss is picked differently, depending on the context.
    """
    bdp = 125.0 * ev["target_rate"] * ev["target_rtt"]	# BDP in bytes
    t = bdp/(0.7*mss)
    if t < 1.0:	# don't allow minuscule windows - they cause divide by zero
	t=1.0
    ev["target_runlen"]=int(t*t)
    ev["target_window"]=bdp
    ev["target_runtime"]=t*ev["target_rtt"]	# expected time between losses in ms
 

################################################################
# High level path analysis and user report generation
################################################################
def dd_checkAbort(r):
    return(r[-1]["CountRTT"] < 1);

def dd_checksys(ev, opts):
    """
    Get some information about the system installation and configuration.
    Return a discription of any problems found.   Currently reports:
	server window too small for the requested test.
    """
    # if already set, return prior result
    if "gate_checksys" in ev:
	return ev["gate_checksys"]

    ev["version_kernel"]=getproc("/proc/version")
    ev["version_web100"]=getproc("/proc/web100/header")
    ev["version_pathdiag"]=version
    ev["config_tcp_rmem"]=getproc("/proc/sys/net/ipv4/tcp_rmem")
    ev["config_tcp_wmem"]=getproc("/proc/sys/net/ipv4/tcp_wmem")
    ev["config_tcp_CC"]=getproc("/proc/sys/net/ipv4/tcp_congestion_control")

    # Allow all CC for the time being  XXX
    #if ev["config_tcp_CC"] != "reno" and ev["config_tcp_CC"] != "highspeed":
    #	ev["gate_checksys"] = "tcp_CC"
    #	return ev["gate_checksys"]

    if opts.maxwindow:
	maxwindow = opts.maxwindow
    else:
	maxwindow = int(ev["config_tcp_wmem"].split("\t")[2])
    needwin = 125*ev["target_rate"]*ev["target_rtt"]*2	# factor of 2 margin
    if needwin > maxwindow:
	ev["gate_checksys"] = "maxwindow %s"%maxwindow
	pp.runlog("E", "Requested DBP exceeds %s"%maxwindow)
	return ev["gate_checksys"]

    return None

def dd_checkSpanRTT(ev, r):
    """ Check the span RTT, return true if too large """
    global duration

    if not duration:	# XXX busted scope
	duration = pp.OneSec

    return(2000*ev["stepsize"]*ev["min_rtt"] > duration)

def dd_openpeerbox(ev, s, pipesize):
    """
    Check to see if the TCP connection properly negotiated required HS features

    Tests include SACK, timestamps, and sufficient window scale for the expected
    window size.  The actual window is not checked because it may be dynamic and
    would therefore be raised later.
    """
    pipesize=pipesize*2	# include the path plus queues
    wscale=0
    bx=ph.boxstart()

    stat=""
    if s["SACKEnabled"] != 3:
        ph.boxmessage(bx, "warning peerNoSACK")
        stat = "warning"
    if s["TimestampsEnabled"] != 1:
        ph.boxmessage(bx, "warning peerNoTS")
        stat = "warning"
    while pipesize > 65536:
        pipesize, wscale = pipesize/2, wscale+1
    wsRcvd=s["WinScaleRcvd"]
    if wsRcvd > 14:
	wsRcvd = -1
    if wscale == 0 and wsRcvd == -1:
	pass	# ignore not requested if not needed
    elif wscale > wsRcvd:
        stat = "fail"
	if wsRcvd == -1:
	    ph.boxmessage(bx, "fail peerNoWS wscale=%d"%(wscale))
	else:
	    ph.boxmessage(bx, "fail peerSmallWS wsrcvd=%d wscale=%d"%(wsRcvd, wscale))

    if not stat:
	ph.boxmessage(bx, "pass peerPassSYN wscale=%d"%wsRcvd)
	stat="pass"

    # note that peer problems can be detected later
    ev["peerbox"] = bx
    ev["peerstat"] = stat
    return(bx, stat)

def dd_closepeerbox(ev):
    bx = ev["peerbox"]
    stat = ev["peerstat"]
    if stat == "pass":
	ph.boxmessage(bx, [stat, "peerPass"])
    else:
	ph.boxmessage(bx, [stat, "peerDiagnosis"])
	if stat == "warning":
	    ph.boxmessage(bx, [stat, "peerWarn"])
	ph.boxmessage(bx, ["action", "peerFix"])
	setexit_receiver()
    ph.boxpush(bx, "section peerTitle status="+stat.capitalize())
    ph.boxpush(bx, "openbox - type="+stat)
    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_opentesterbox(ev):
    """
    opentesterbox - Report the following classes of tester problems:

    Instrumented problems with the tester itself -
    	e.g. sender bottlenecks or pauses
	These are explicitly detected, but may be overly sensitive
    Observed problems with instrumentation or analysis - 
    	e.g. MBZ instruments without further explanation or failed internal consistency checks
	These are explicitly flagged by the global "exceptional"
    Failing test process -
	Insufficient time or other "environmental" limitation prevented a complete test
	Note that these are not really a tester failure, but it looks like one
    Unknown flaw in TCP or the tester itself
    	E.g. any TCP bug that requires TCP dump to find

    """
    bx = ph.boxstart()
    stat="pass"

    # note that tester problems can be detected later
    ev["testerbox"] = bx
    ev["testerstat"] = stat
    return(bx, stat)

def dd_closetesterbox(ev):
    global exceptional
    bx = ev["testerbox"]
    stat = ev["testerstat"]
    if exceptional:
	setexit_unknown()
	if stat != "fail": stat = "warning"
	ph.boxmessage(bx, stat+" testerUndiagnosed")
    if stat == "pass":
	ph.boxmessage(bx, "pass testerPass")
    else:
	basename=options.logbase.split("/")[-1]		# XXX scope
	ph.boxmessage(bx, "action testerUnknownFix filename="+basename+".html")
    if ev["version_pathdiag"] != version:
#	print ">%s< >%s<"%(ev["version_pathdiag"], version)
	ph.boxmessage(bx, ["info", "testerVersion", "version="+ev["version_pathdiag"], "phase=Collector"])
    ph.boxmessage(bx, ["info", "testerVersion", "version="+version, "phase=Tester"])
    ph.boxpush(bx, "section testerTitle status="+stat.capitalize())
    ph.boxpush(bx, "openbox - type="+stat)
    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_checkother(ev, bx, problem=None):
    """
	Report all non-path bottlenecks

	This is called after it is determined that some test failed
	(e.g did not attain the required data rate or actual window size)
	to check for any problems detected by di_other().

	If there seems to be a problem, show the messages only once and
	return True.
    """
    global exceptional

    if not problem:
	problem=ev["maxrate"]

    explained=False
    # target (peer) problems such as receiver window too small
    if "bx_target" in problem:
	ph.boxmerge(ev["peerbox"], problem["bx_target"], dupcheck=True)
	stat=problem["bx_target"][0].split(" ")[0]
	if ev["peerstat"] != "fail":
	    ev["peerstat"]=stat
	setexit_receiver()
	explained = True
    # tester problems such as not keeping up with the path
    if "bx_tester" in problem:
	ph.boxmerge(ev["testerbox"], problem["bx_tester"], dupcheck=True)
	ev["testerstat"] = "warning"
	setexit_sender()
	explained = True
    # unknow tester events: fail MBZ counters, etc.   These should all evolve to explicit tests
    if "bx_diag" in problem:
	ph.boxmerge(ev["testerbox"], problem["bx_diag"], dupcheck=True)
	ev["testerstat"] = "warning"
	exceptional = True
	explained = True
# consistency check on di_other[1] - it must agree with "explained"
    if problem["di_other"][1]:
	if not explained:
	    ph.boxmessage(ev["testerbox"], ["warning", "testerInconsistent", "reason=di_other",
			  "message="+problem["di_other"][1]])
	    ev["testerstat"] = "warning"
	    exceptional = True
    else:
	if explained:
	    ph.boxmessage(ev["testerbox"], ["fail", "testerInconsistent", "reason=not_di_other", "message="])
	    ev["testerstat"] = "fail"
	    exceptional = True
    # if the path is too long, don't give other details
    if "longspan" in ev:
	explained = True
    # also check to see if data rate or loss rate tests failed
    if "pathstat" in ev and ev["pathstat"] == "fail":
	explained = True
    # Report that this test was spoiled
    if explained:
	ph.boxmessage(bx, "warning GenericIncomplete")
	ph.boxmessage(bx, "action GenericFix")
    return explained

def dd_insufficient(ev, bx, loss=False):
    """
    Try to explain why we failed to collect sufficient data for
    some measurement.
    """
    global exceptional
    if loss and "rescan" in ev and ev["rescan"] == "different":
	pass # be silent on tests with altered parameters
    else:
	ph.boxmessage(bx, "fail testerInsufficientUnknown")
	exceptional = True

def dd_checkrate(ev):
    " check the data rate "
    bx = ph.boxstart()
    if ev["maxrate"]["rate"] < ev["target_rate"]:
	stat="fail"
	ph.boxmessage(bx, "fail rateMeasured rate=%f"%(ev["maxrate"]["rate"]))
	ph.boxmessage(bx, "fail rateTarget rate=%f"%(ev["target_rate"]))
	if ev["lossCnt"]:
	    lm = fitSqrt(ev["lossRTTsum"]/ev["lossCnt"], ev["lossDuration"], ev["losspkts"], ev["lossretrans"])
	else: lm= 0.0
        if dd_checkother(ev, bx):
	    pass
	elif lm > 0.5:
	    ph.boxmessage(bx, "fail rateLoss")
	else:
	    # XXX should check for multiple samples at the same rate
	    ph.boxmessage(bx, "fail rateClamp")
	    if ev["maxrate"]["rate"] > 0.9*ev["target_rate"]:
		ph.boxmessage(bx, "action rateOverhead")
	    ph.boxmessage(bx, "action rateRoute")
	    setexit_path()
	ev["pathstat"]=stat	# MUST be after dd_checkother()
    else:
	stat="pass"
	ph.boxmessage(bx, "pass ratePass rate=%f"%(ev["maxrate"]["rate"]))
    ph.boxpush(bx, "section rateTitle status="+stat.capitalize())
    ph.boxpush(bx, "openbox - type="+stat)
    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_checkloss(ev):
    "Check Uncongested loss rate"
    bx = ph.boxstart()
    if ev["lossCS"] < 4 and ev["losspkts"] < 2*ev["target_runlen"]:
	stat="warning"
	if ev["pathstat"] != "fail": ev["pathstat"]="warning"
        if ev["lossCS"] == 0 and ev["losspkts"] < ev["target_runlen"]:
	    ph.boxmessage(bx, "warning lossInsufficient0 have=%d need=%d"%(ev["losspkts"], ev["target_runlen"]))
	else:
	    ph.boxmessage(bx, "warning lossInsufficient")
	# now comment on why insufficient data
	if 2*ev["maxpower"]["rate"]<=ev["target_rate"]:
	    ph.boxmessage(bx, "warning lossInsufficientRate")
	    ph.boxmessage(bx, "action lossInsufficientRateFix")
	    ev["hopeless"]=True		# don't try further (harder) tests
	else:
	    dd_insufficient(ev, bx, True)

    if ev["lossCS"] or ev["losspkts"] > ev["target_runlen"]:
	runlen = div(1.0*ev["losspkts"], ev["lossCS"], ev["losspkts"])
	ev["best_runlen"] = runlen
	lossrate = div(1.0*ev["lossretrans"], ev["lossCS"], 1.0)
	if runlen < ev["target_runlen"]:
	    stat="fail"
	    ev["pathstat"]=stat
	    ph.boxmessage(bx, "fail lossFail percent=%f runlen=%d"%(100.0/runlen, int(runlen)))
	    ph.boxmessage(bx, "fail lossDiagnosis")
	    ph.boxmessage(bx, "fail lossDetails count=%f percent=%f"%(lossrate, 100.0*lossrate/runlen))
	    ph.boxmessage(bx, stat+" lossBudget rate=%d mss=%d rtt=%d percent=%f runlen=%d"%\
			  (ev["target_rate"], ev["maxpower"]["CurMSS"], ev["target_rtt"], 100.0/ev["target_runlen"], ev["target_runlen"]))
	    ph.boxmessage(bx, "action lossAction")
	else:
	    stat="pass"
	    if ev["lossCS"]:
		ph.boxmessage(bx, "pass lossPass percent=%f runlen=%d"%(100.0/runlen, int(runlen)))
	    else:
		ph.boxmessage(bx, "pass lossPass0 percent=%f runlen=%d"%(100.0/runlen, int(runlen)))
	    ph.boxmessage(bx, stat+" lossBudget rate=%d mss=%d rtt=%d percent=%f runlen=%d"%\
			  (ev["target_rate"], ev["maxpower"]["CurMSS"], ev["target_rtt"], 100.0/ev["target_runlen"], ev["target_runlen"]))
    ph.boxpush(bx, "section lossTitle status="+stat.capitalize())
    ph.boxpush(bx, "openbox - type="+stat)
    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_checkduplex(ev, res):
    "check duplex missmatch"
    bx = ph.boxstart()
    if "scan_duplex" in ev or ev["maxrate"]["awnd"] <= 4:
	if "scan_duplex" in ev:
	    doduplex = True
	elif "gate_duplex" in ev:
	    doduplex = False
	else:
	    visited = {}
	    for s in res:
		visited[s["win"]] = True
	    for w in range(3,11):
		if not w in visited:
		    doduplex = False
		    break
	    else:
		doduplex = True
	# check first
	if doduplex:
	    if ev["lossyDuration"] and \
		    ev["maxrate"]["rate"] > 2.0 * (8.0 * ev["lossyBytesAcked"] / ev["lossyDuration"] ):
		ph.boxmessage(bx, "fail duplexDiagnosis")
		ph.boxmessage(bx, "action duplexFix")
		stat="fail"
		ev["pathstat"] = "fail"
		ev["hopeless"]=True
	    else:
		ph.boxmessage(bx, "pass duplexCheck")
		stat="pass"

	    ph.boxpush(bx, "section duplexTitle status="+stat.capitalize())
	    ph.boxpush(bx, "openbox - type="+stat)
	    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_checkstatic(ev):
    "check static queue length "
    bx = ph.boxstart()
    stat="pass"
    # Should be "fail to meet pre-conditions for queue test"
    if "hopeless" in ev or not "maxlaminar" in ev:
	return(bx) # a null box
    ml=ev["maxlaminar"]
    mp=ev["maxpower"]

    qpkts=ml["awnd"]-mp["awnd"]
    qbytes=qpkts*mp["CurMSS"]
    qtime = ml["avg_rtt"]-mp["avg_rtt"]
    queueneeded = 125.0 * ev["target_rate"] * ev["target_rtt"]  # in bytes
    # saturated indicates that we probably found queue full
    saturated = ev["saturatedCnt"] >= 3
    # otherbottlneck indicates that we have already found other problems
    # ann issued an action
    otherbottleneck = dd_checkother(ev, bx, ml) # XXX should be ml+1...
    if qbytes < 0:
	ph.boxmessage(bx, "fail staticNegative")
	ph.boxmessage(bx, "fail staticMeasured packets=%d bytes=%d"%(qpkts, qbytes))
	if not saturated:
	    pass # XXX logically inconsistent
	stat="fail"
	ev["pathstat"] = "fail"
	setexit_path()  # XXX redundant
    elif qbytes < queueneeded:
	if otherbottleneck:
	    ph.boxmessage(bx, "warning staticEstimated packets=%d bytes=%d"%(qpkts, qbytes))
	    stat="warning"
	else:
	    if saturated:
		ph.boxmessage(bx, "fail staticDiagnosis")
		stat="fail"
	    else:
		stat="warning"
		if ev["pathstat"] == "pass": 	# XXX overly simplistic
		    ph.boxmessage(bx, "warning staticTooFast")
		else:
		    dd_insufficient(ev, bx)
	    ph.boxmessage(bx, "warning staticEstimated packets=%d bytes=%d"%(qpkts, qbytes))
	if qtime > 0.0:
	    ph.boxmessage(bx, "info staticQueueTime time=%f"%(qtime))
	if ev["pathstat"] != "fail": ev["pathstat"]=stat
	ph.boxmessage(bx, "warning staticInfo rate=%d rtt=%d bytes=%d"\
		      %(ev["target_rate"], ev["target_rtt"], queueneeded))
	if stat == "fail":
	    ph.boxmessage(bx, "action staticFix maxjitter=%f"%( qtime ))
	setexit_path()  # XXX redundant
    else:
	ph.boxmessage(bx, "pass staticPass")
	stat2="pass"
	if not saturated or otherbottleneck:
	    ph.boxmessage(bx, "warning staticEstimated packets=%d bytes=%d"%(qpkts, qbytes))
	    stat2="warning"
	    # XXX, but otherbottleneck generated a spurious failed host tuning message
	else:
	    ph.boxmessage(bx, "pass staticMeasured packets=%d bytes=%d"%(qpkts, qbytes))
	if qtime > 0.0:
	    ph.boxmessage(bx, stat2+" staticQueueTime time=%f"%(qtime))
	ph.boxmessage(bx, "pass staticInfo rate=%d rtt=%d bytes=%d"\
		      %(ev["target_rate"], ev["target_rtt"], queueneeded))
    ph.boxpush(bx, "section staticTitle status="+stat.capitalize())
    ph.boxpush(bx, "openbox - type="+stat)
    ph.boxmessage(bx, "closebox")
    return(bx)

def dd_checkburst(ev):
    pass

def dd_pathsuggestions(ev):
# suggest alternate tests
    bx = ph.boxstart()
    if not "hopeless" in ev and "best_runlen" in ev:
	ph.boxmessage(bx, "openbox - type=info")
	ph.boxmessage(bx, "section altTitle")
	best_runlen=ev["best_runlen"]
	best_rate=ev["maxrate"]["rate"]
	if "pathstat" in ev and ev["pathstat"] == "pass": # XXX what about warnings?
	    ph.boxmessage(bx, "info altStronger")
	else:
	    ph.boxmessage(bx, "info altWeaker")
	if int(best_rate) > int(ev["target_rate"]):
	    improve(bx, ev["maxrate"], best_runlen, rate=ev["target_rate"])
	improve(bx, ev["maxrate"], best_runlen)
	if ev["maxrate"]["CurMSS"] < 9000:
	    ph.boxmessage(bx, "info altRaiseMSS")
	    if int(best_rate) > int(ev["target_rate"]):
	    	improve(bx, ev["maxrate"], best_runlen, rate=ev["target_rate"], mss=9000)
	    improve(bx, ev["maxrate"], best_runlen, mss=9000)
	ph.boxmessage(bx, "closebox")
    return(bx)

def improve(bx, s, rl, rate=0, mss=0):
    if not rate:
	rate=s["rate"]
    m=mss
    if not mss:
	m=s["CurMSS"]
    rtt=int(0.7*0.001*8*m/rate*math.sqrt(rl))
    if mss:
	ph.boxmessage(bx, "info altMSSTest rate=%d rtt=%d mss=%d"%(rate, rtt, mss))
    else:
	ph.boxmessage(bx, "info altTest rate=%d rtt=%d"%(rate, rtt))

def dd_user(ev, res):
    """
	Display a user friendly report
    """
    # open the test information box
    infobox=ph.boxstart()
    ph.boxmessage(infobox, "openbox - type=info")
    ph.boxmessage(infobox, "section testTitle")
    s=res[-1]
    ph.boxmessage(infobox, "info testTester hostname=%s address=%s"%(socket.getfqdn(s["LocalAddress"]), s["LocalAddress"]))
    ph.boxmessage(infobox, "info testTarget hostname=%s address=%s"%(socket.getfqdn(s["RemAddress"]), s["RemAddress"]))
    basename=options.logbase.split("/")[-1]		# XXX scope
    ph.boxmessage(infobox, "info testLogbase filename="+basename)

    # display the target rate
    ph.boxmessage(infobox, "info testTargetRate rate=%d"%(ev["target_rate"]))
    if "orig_target_rate" in ev:
	ph.boxmessage(infobox, "info testReRate rate=%d"%(ev["orig_target_rate"]))

    # display target rtt
    if ev["min_rtt"] > ev["target_rtt"]:
	ph.boxmessage(infobox, "warning testRTTwarn segrtt=%d rtt=%d"%(ev["min_rtt"], ev["target_rtt"]))
	if not "orig_target_rtt" in ev:
	    ev["orig_target_rtt"] = ev["target_rtt"]
	    ev["target_rtt"] = int(ev["min_rtt"])+1 # if previously overridden, don't override again
    ph.boxmessage(infobox, "info testTargetRTT rtt=%d"%(ev["target_rtt"]))
    if "orig_target_rtt" in ev:
	ph.boxmessage(infobox, "info testReRTT rtt=%d"%(ev["orig_target_rtt"]))

    # Display the section MSS and RTT
    ph.boxmessage(infobox, "info testPath mss=%d rtt=%6f"%(s["CurMSS"], ev["min_rtt"] ))

    # Display the TOS if it was set
    if "set_tos" in ev:
        ph.boxmessage(infobox, "info testTOS tos=%d"%(ev["set_tos"]))

    # open 3 main boxes
    dd_openpeerbox(ev, res[1],  125.0 * ev["target_rate"] * ev["target_rtt"])
    dd_opentesterbox(ev)
    pathbox=ph.boxstart()
    ph.boxmessage(pathbox, "section pathTitle")
    ev["pathstat"]="pass"
    # path checks below may add messages to any of the 3 main boxes

    # First check to see if the test even ran on this span
    if dd_checkAbort(res):
	ph.boxmessage(pathbox, "warning pathAborted")
	ev["pathstat"]="warning"
    elif "gate_checksys" in ev:
	checksys = ev["gate_checksys"].split(" ")
	if checksys[0] == "maxwindow":
	    ph.boxmessage(pathbox, "warning pathWindow rate=%s rtt=%s"%(ev["target_rate"], ev["target_rtt"]))  # XXX orig_?
	    ph.boxmessage(pathbox, "action pathReduce size=%s"%checksys[1])
	else:
	    raise "gate_checksys"
	ev["pathstat"]="warning"
    else:
	# We can still run get some data if the span was too long
	if dd_checkSpanRTT(ev, res):
	    ph.boxmessage(pathbox, "warning pathLength")
	    ph.boxmessage(pathbox, "action pathChoose")
	    ev["longspan"]=True
	ph.boxmerge(pathbox, dd_checkrate(ev))
	ph.boxmerge(pathbox, dd_checkloss(ev))
	ph.boxmerge(pathbox, dd_checkduplex(ev, res))
	ph.boxmerge(pathbox, dd_pathsuggestions(ev))
	ph.boxmerge(pathbox, dd_checkstatic(ev))
#    dd_checkburst(ev)

    # summarize all path problems
	if ev["pathstat"] == "pass":
	    ph.boxmessage(pathbox, "pass pathPass")
	elif ev["pathstat"] == "fail":
	    ph.boxmessage(pathbox, "action pathFix")
	    setexit_path()
    ph.boxpush(pathbox, "openbox - type="+ev["pathstat"])
    ph.boxmessage(pathbox, "closebox")

# merge into the outer info box
    ph.boxmerge(infobox, dd_closepeerbox(ev))
    ph.boxmerge(infobox, pathbox)
    ph.boxmerge(infobox, dd_closetesterbox(ev))
    if options.plot:
	ph.boxmessage(infobox, "info testPlotHere filename="+basename)
    ph.boxmessage(infobox, "closebox")

# Make it into a complete page.  XXX This belongs in an outer scope
# since the I may be combining reports into a larger page.
    page=ph.boxstart()
    ph.boxmessage(page, "beginpage")
    ph.boxmerge(page, infobox)
    ph.boxmessage(page, "endpage")
#    ph._boxlist(page)
    return(page)

def dd_emitreport(ev, page, opts, run=None):
    """ Convert a report script into the requested formats """

# Plot here so we can insert graphs into the report
    global plotok
    if opts.plot:
	dd_showhead()
    	plotf=open(opts.logbase+".plt", "w") # tabbular data
    	for s in pp.allRuns[1:]:
	    if s["win"] and s["flag"]:	# exclude noise
	    	dd_report(s, ev, opts.plot.split(","), plot=True, outf=plotf)
    	plotf.close()

	# XXX gnuplot errors go to stderror and are not trapped
	if plotok and opts.plot == "yes":
	    try:
		g = Gnuplot.Gnuplot()
		g(gnuplotcmds.replace("FILE", opts.logbase))
	    except:
		plotok=False

# if extra verbose, show the raw page
    if opts.verbose > 1:
	for p in page:
	    print p
# Does not yet parse options
# First, regular html report
    messages=ph.getmessages("default.fmt")
    formats=ph.getformats("default.fmt")
    help=ph.gethelp("default.fmt")
    hfile=open(opts.logbase+".html", "w")
    ph.boxhtml(hfile, page, formats, messages, help)
    hfile.close()
# Iff this is a live run, same output to .live for later regression testing
    if run:
	hfile=open(opts.logbase+".live", "w")
	ph.boxhtml(hfile, page, formats, messages, help)
	hfile.close()
#second, a server summary table fragment
    messages=ph.getmessages("summary.fmt")
    formats=ph.getformats("summary.fmt")
    hfile=open(opts.logbase+"smry.html", "w")
    ph.boxhtml(hfile, page, formats, messages)
    hfile.close()
# third, look at the requested format
# XXX should loop, looking for multiple formats
    if opts.format == "trace":
	messages=ph.getmessages("trace.fmt")
	formats=ph.getformats("trace.fmt")
	hfile=open(opts.logbase+"trace.dat", "w")
	ph.boxhtml(hfile, page, formats, messages)
	hfile.close()

################################################################
# Table format output (-v switch, etc)
################################################################
needhead = 0

def dd_showhead():
    """ Cause the dd_show to emit a header line """
    global needhead
    needhead = 1

def dd_verbosity():
    """
    Pick the default table format on the basis of verbosity
    """
    if options.verbose>1:
	return(["di_stats", "di_PF", "di_laminar", "di_other"])
    elif options.verbose:
	return(["di_stats", "di_PF", "di_other"])
    else:
	return(None)

plothelp = """Usage for: --plot=keyword1,keyord2[... ,keywordN]
Generates unsorted file <logbase>.plt   Some useful keywords:
awnd	Actual (observed) window
rate	Date rate in bits per second
rtt	Average RTT computed from window/rate
power	Rate/RTT
cong	Congestion signals (e.g. packet losses) per interval
basic	Shorthand for: awnd,rate,rtt,power,cong
Plus all web100 variables by their own names (E.g. SmoothedRTT) and
internal per sample variables.  The exaustive list includes:"""
tablehelp = """With -R, many additional columns can be added to the table format
by adding key words to the command line.  Some useful keywords:
ALL	Dumps everything (too big to be useful)
Xtctrl	Testing engine regular controls
Xburst	Testing engine burst controls
Xtriage	All 6 triage instruments
Xrtt	Additional RTT estimators
Plus all web100 variables by their own names.  (E.g. SmoothedRTT)
and most internal objects.  The exaustive list includes:"""
# Some useful table formats
formats={}
formats["default"] = [ "di_stats", "di_other" ]
formats["ALL"] = "hard coded"
formats["Xtctrl"] = [ "flag", "basemss", "duration", "SSbursts", "SSbully", "SSbullyStall", "SSsumAwnd", "SScntAwnd", "SSpoll" ]
formats["Xtriage"] = [ "SndLimTimeRwin", "SndLimBytesRwin", "SndLimTransRwin", "SndLimTimeCwnd", "SndLimBytesCwnd", "SndLimTransCwnd", "SndLimTimeSender", "SndLimBytesSender", "SndLimTransSender" ]
formats["Xburst"] = ["SSpoll", "SSbursts", "SSbully", "SSbullyStall" ]
formats["Xrtt"] = ["vir_rtt", "win_rtt"]
# Sume useful plot formats
formats["cong"] = ["CongestionSignals"]
formats["rtt"] = ["avg_rtt"]
formats["basic"] = ["awnd", "rate", "rtt", "power", "cong" ]
formats["yes"] = ["awnd", "rate", "rtt", "power", "cong" ]   # Hard coded, generate graphs
# multiple future report formats
namehelp=True

# gnuplot command script.  Substitute filename for FILE
gnuplotcmds="""
set terminal png size 600, 450
set nokey
set yrange [0:*]
set xlabel "Window (packets)"

set output "FILErate.png"
set ylabel "Data Rate (Mb/s)"
plot "FILE.plt" using 1:2

set output "FILErtt.png"
set ylabel "RTT (ms)"
plot "FILE.plt" using 1:3

set output "FILEpow.png"
set ylabel "Power (segs/sec/sec)
plot "FILE.plt" using 1:4

set yrange [0:2.5]
set output "FILEloss.png"
set ylabel "losses (segments)"
plot "FILE.plt" using 1:5

"""

def dd_report(s, ev, fmt=["default"], plot=None, outf=sys.stdout):
    """ Display messages that have been placed in the dictionary """

    if plot:
	sep,undef = "\t", "-0"	# can exclude later
    else:
	sep,undef = " ", "-?-"

    global needhead, namehelp
    r=("","","")

    lf=fmt[:]
    while len(lf):
        f=lf.pop(0)
	if f == "ALL":				# ALL
	    lf[:0] = s.keys()
	elif f in s:				# in the snap (including added symbols)
            val=s[f]
	    if isinstance(val, TupleType):
		r=dd_merge(r, val)
	    else:
		r=dd_merge(r, sep+f, sep+str(val), "")
	elif f in formats:			# in a format macro
	    lf[:0]=formats[f]
	elif f in ev:				# in the event list
	    val=ev[f]
	    try:
		val = "Row:%d"%val["row"]
	    except TypeError:
		pass
	    r=dd_merge(r, sep+f, sep+str(val), "")
	else:					# unknown name
	    if namehelp:
		namehelp=False
		# XXX these go to stdout??
		if plot:
		    print plothelp
		    print " ".join(s.keys())
		else:
		    print tablehelp
		    print " ".join(s.keys()), " ".join(ev.keys())
	    r=dd_merge(r, sep+f, sep+undef, "")

    # output the report
    head, line, mess = r
    if needhead:
        outf.write("#%s\n"%head)
        needhead = 0
    outf.write(line+"\n") 
    # footnotes, etc only to stdout XXX
    if mess and outf == sys.stdout:
	outf.write(mess)


def showallvars(d):
    """
    Dump out everything in the dictionary for a sample.

    Pretty useless except for debugging
    """
    for k in d.keys():
	print k, d[k]   

################################################################
# Single sample diagnostic checks.  All di_ method leave all results
#	in the dictionary, including pre-formatted report fragments, etc.
################################################################
def dd_merge(r, h, v=None, m=None):
    """
    A helper routine to manage 3 parallel outputs: titles, values, and footnotes
    """
    if r:
	h0, v0, m0 = r
    else:
	h0, v0, m0 = "", "", ""
    if not isinstance(h, StringTypes):
	h, v, m = h
    return((h0+h), (v0+v), (m0+m))

def footnote(ev, v, m, tag, text, val=None):
    """
	Manage footnotes for diagnostic tests

	Footnotes improve readability by suppressing otherwise duplicate
	messages from the tests.  This permits long and clear messages for
        infrequent events without reducing the overall readability of
	the output.
    """
    if not "footlist" in ev:
	ev["footlist"] = {}
    if tag in ev["footlist"]:
        if ev["footlist"][tag] != text:
            raise "botched footnote"
    else:
        ev["footlist"][tag] = text
        m = m + "*%s: "%tag + text
    fn = " *%s"%tag
    if val:
        fn += ":%d"%val
    return ( (v + fn, m) )

def di_stats(s, ev):	# show control fields
    """ show basic test parameters """

# window control calibration checks
    # obswin is max of SndNxt - SndUna (but may not properly mask recoverys)
    s["obswinpkts"] = s["obswin"] / s["CurMSS"]
    # estimate actual window (awnd) to be the minimum of the observed and control windowd
    # This is a workaround for SndNxt - SndUna including retransmissions
    awnd = s["obswinpkts"]
    if s["win"] and awnd > s["win"]:
	awnd = s["win"]
    s["awnd"] = awnd
    # same but averaged instead of max (Not used)
#    s["avg_obswin"] = div(s["SSsumAwnd"], s["SScntAwnd"], 0)

# useful general stats: data rate in bits per second and run length = 1/losses
#    s["rate"] = div( 8.0 * s["ThruBytesAcked"], s["Duration"], 99999.0)
    s["rate"] = div( 8.0 * s["SndUna"], s["Duration"], 99999.0)
    s["runlen"] = div( s["DataPktsOut"], s["CongestionSignals"], s["DataPktsOut"])

# RTT
    # window RTT is computed from the data rate
    s["win_rtt"] = div(s["Duration"] / 1000.0 * s["awnd"], s["DataPktsOut"])
    # virtual rtt includes the delay that we added to cause bursts
#    s["vir_rtt"] = s["tcp_rtt"] + 8.0 * s["CurMSS"] * s["burstwin"] / ev["target_rate"] / 1000.0

    # average rtt (used throughout the rest of the analysis), guess which is better
    if s["flag"] and s["DataPktsOut"] > 100:
	s["avg_rtt"] = s["win_rtt"]
    else:
	s["avg_rtt"] = s["SmoothedRTT"]	# directly from the kernel

    # find the minimum RTT
#   if not "min_rtt" in ev or ev["min_rtt"] > s["avg_rtt"]:
#	ev["min_rtt"] = s["avg_rtt"]
    ev["min_rtt"] = s["MinRTT"] # use the kernels minimum, may be low because SYNs are small

# Power
    s["power"]=div(1000000.0*s["rate"],(s["avg_rtt"]*s["Duration"]), -1)

# pre-format fragments
    cs = s["CongestionSignals"]
    if cs == 0:
        runlens = ">"
    elif cs < 5:
        runlens = "~"
    else:
        runlens = "="

    head = "fg    win burst awnd :"
    val =  "s:%2d %4d %3d %6d :"%(s["flag"], s["win"], s["burstwin"], s["awnd"])
    r = ( head, val, "")

    head = "    rate pktsout  CS   runlen    RTT "
    val = " %7.2f %7d %3d %1s %6d %6.4f"%(s["rate"], s["DataPktsOut"], cs, runlens, s["runlen"], s["avg_rtt"])

# Useful fragments
#    val += " %6.4f %6.4f"%( s["win_rtt"], s["win_rtt"]-s["avg_rtt"] )
#    i = s["ThruBytesAcked"]
#    val += " %X %X"%(s["ThruBytesAcked"], i)

    s["di_stats"] = dd_merge(r, head, val, "")

def di_pf(s, ev, Trate=None, Trunlen=None):
    """
	First cut pass/fail test and initial diagnosis

	Note that unlike other tests, this test is relative to target
	data rate and run length (1/loss rate), which must be specified
	external to this test.
    """
    grade, message = "", ""
    if not Trate:
	if "target_rate" in ev:
	    Trate=ev["target_rate"]
	else:
	    grade = "Z"
    if not Trunlen:
	if "target_runlen" in ev:
	    Trunlen=ev["target_runlen"]
	else:
	    grade = "Z"

    # partition into 4 quadrants by rate and runlen
    #		note runlen = DataPktsOut if no recoveries
    FUDGE = 0.98	# Vague: check to see if lossless rate matches window
    if grade:
	pass
    elif s["rate"] > Trate:
        if s["runlen"] > Trunlen:
            grade = "P"		# Pass
        elif s["CongestionSignals"]:
            grade = "L"		# meets rate, but too much loss
        else:
	    grade = "?"		# sample too short
    else:
        if s["CongestionSignals"]:
            grade = "F"		# Fail outright
        else:
            # did not meet rate even though no loss
            if s["rate"] < FUDGE*8.0/1000.0*div((s["awnd"]-1)*s["CurMSS"],s["avg_rtt"],0.0):
                grade = "X"		# some unknown bottleneck
            elif s["DataPktsOut"] > Trunlen:
                grade = "<"		# Beat Trunlen because window is too small
            else:
                grade = "?"		# sample is too small

    s["grade"]=grade
    head = " ?"
    val = "%2s"%grade
    s["di_PF"]=( head, val, message)

def di_resetscan(ev):
    """
    Reset all state variables that are used to squelch scanning beyond
    bottlenecks.
    
    This must be done everytime the window is deliberately reduced.
    """
    if "lagging" in ev:
	del ev["lagging"]
    if "throttle" in ev:
	del ev["throttle"]
    if "maxawnd" in ev:
	del ev["maxawnd"]
    if "choke" in ev:
	del ev["choke"]

def history(pred, ev, sn, th):
    """
    Implement hysteresis:

    Return true if (pred) is true (th) times counted in (ev[sn])
    """
    if pred:
	if not sn in ev:
	    ev[sn] = 1
	else:
	    ev[sn] += 1
	    if ev[sn] >= th:
		return True
    else:
	if sn in ev:
	    del ev[sn]
    return False

def di_resetloss(ev, lw=0):
    # aggregate stats of the uncongested part of the test
    if "losswindow" in ev:
	del ev["losswindow"]
    if lw:
	ev["losswindow"] = lw
    ev["losspkts"] = 0
    ev["lossretrans"] = 0
    ev["lossCS"] = 0
    ev["lossRTTsum"] = 0
    ev["lossCnt"] = 0
    ev["lossDuration"] = 0
    ev["lossyBytesAcked"] = 0
    ev["lossyDuration"] = 0
    ev["saturatedCnt"] = 0

def di_laminar(s, ev):
    """
	Do a static queue measurement using a standing queue

	This test uses a laminar packet flow to create a
	standing queue at the bottleneck.   The queue length
	is taken as the difference in window size for the
	maximum power point and the onset of AIMD congestion control.

	Unlike other sample tests, this one assumes a sequence of samples that
	cross the points of interest.

	Identifies important rows (one pass):
	ev["maxrate"]	 Highest data rate
	ev["maxpower"]	 Greatest rate/rtt ratio
	ev["maxlaminar"] Largest non-congested window

	If "losswindow" is set then compute several statistics
	    ev["loss*"] on all samples with smaller windows.     
    """
    # Find the Maximum data rate  (outside of valid check)
    if not "maxrate" in ev or s["rate"] > ev["maxrate"]["rate"]:
	ev["maxrate"] = s

    # valid excludes stabilization intervals and slowstart
    valid = s["win"] and s["flag"]
    if not valid:
	head = "  power fit1"
	val = " %7.2f"%0.0
	val += " %4.2f"%0.0
	s["di_laminar"] = (head, val, "")
	return

    # Find the Maximum power point (queue start knee)
    power=s["power"]
    if not "maxpower" in ev or power > ev["maxpower"]["power"]:
	ev["maxpower"] = s

    # Find the largest window that has less loss than the short span model
    # XXX this also imposes (unchecked) limits on the test parameters and the RTT
    # Note that if the section RTT is significant, this is the same as the largest window
    # with no losses
    linkmodel = s["linkmodel"] = \
	fitSqrt(s["avg_rtt"], s["Duration"], s["DataPktsOut"], s["CongestionSignals"])
    if linkmodel < 0.6:
	if not "maxlaminar" in ev or s["awnd"] > ev["maxlaminar"]["awnd"]:
	    ev["maxlaminar"] = s
    else:
	try:
	    ev["saturatedCnt"] += 1
	except:
	    ev["saturatedCnt"] = 1

    # compute loss stats: using loss window which must be computed from a prior pass
    if "losswindow" in ev:
	l = (s["awnd"] <= ev["losswindow"])
	if l: # loss stats below the clift
	    ev["losspkts"] += s["DataPktsOut"]
	    ev["lossretrans"] += s["PktsRetrans"]
	    ev["lossCS"] += s["CongestionSignals"]
	    ev["lossRTTsum"] += s["avg_rtt"]
	    ev["lossCnt"] += 1
	    ev["lossDuration"] += s["Duration"]
	else: # rate stats above the onset of loss
	    ev["lossyBytesAcked"] += s["ThruBytesAcked"]
	    ev["lossyDuration"] += s["Duration"]

    head = "  power fit1"
    val = " %7.2f"%s["power"]
    val += " %4.2f"%linkmodel
    s["di_laminar"] = (head, val, "")

def di_bursts(s):
    """
	Future burst mode test
    """
    pass

def di_mbz(ev, val, mess, s, vl):
    """ Generic Must Be Zero check for all oddball stuff.

	Theses could (should) be replaced by variable specific code
    """
    global exceptional
    for v in vl:
	if s[v]:
	    tag=v
	    exceptional = exceptional or transient
	    val, mess = footnote(ev, val, mess, tag, "Unexpected non-zero statistic*\n", s[v])
	    di_box(s, "bx_diag", "warning testerMBZ varname=%s value=%d"%(v, s[v]))
    return(val, mess)

# lots of corner cases
mbzCC = [ "CurTimeoutCount", "CongestionOverCount", "X_OtherReductionsCV" ]
mbzRP = [ "DataBytesIn", "DataPktsIn" ]

def di_box(s, name, msg):
    "Add a box with an interim report to a snap"
    if not name in s:
	s[name] = ph.boxstart()
    ph.boxmessage(s[name], msg)

def di_other(s, ev):
    """
    Diagnose non-network performance limitations and other test failures.

    This test should *always* be run but should never report anything.
    If it does report something, it is almost certainly reflects a
    problem with the test setup, (e.g. not enough CPU) unrelated to 
    the path itself.

    All of these checks set s[di_...], to be checked later by dd_checkother().
        Thus transient events may go unreported.
    s["bx_target"] - Indicates a problem with the target
    s["bx_tester"] - Indicates a problem with the tester
    s["bx_diag"]   - Indicates a problem that is un-known or in the diagnostic algorithm itself.
    We also set ev["choke"], ev["throttle"] if these seem to stop this scan
    or ev["punt"] if the connection is dead (or out of time).    
    """

    why = message = val = ""
    if "grade" in s:
	why=s["grade"]
	if why != "X":	# if di_pf was "X", the problem is here
	    why = ""	# otherwise, we are just double checking

    global exceptional
    triagetotal = (s["SndLimTimeSender"] +
                   s["SndLimTimeCwnd"] +
                   s["SndLimTimeRwin"])

    # check receiver limited
    i = s["SndLimTimeRwin"]
    if i:
        val, message = footnote(ev, val, message, "RW",
                                "Percent time receiver window limited\n",
                                100.0 * i / triagetotal)
        crwin = s["CurRwinRcvd"]
        mrwin = s["MaxRwinRcvd"]
	if s["win"]:
	    w = s["win"]*s["CurMSS"]
	else:
	    w = (s["awnd"]+1)*s["CurMSS"]	# slowstart/prescan
	    if "target_window" in ev and w > ev["target_window"]:
		w = ev["target_window"]		# slowstart window was larger than target DBP
	if mrwin < w:		# MAX rwin is to small
	    if mrwin == 0:
		di_box(s, "bx_tester", "warning testerWeb100zeroRwin");
            i = mrwin/1024
            tag="MAXrwin%d"%i
	    if "target_window" in ev and ev["target_window"] < mrwin:
		val, message = footnote(ev, val, message, tag+"test",
                                   "Maximum receiver window (%dk) is too small for this test\n"%i)
		di_box(s, "bx_target", "warning peerMaxRwinOK val="+str(i))
	    elif s["win"] == 0 and not "target_window" in ev:
		val, message = footnote(ev, val, message, tag+"ss",
                                   "Maximum receiver window (%dk) limited initial slowstart\n"%i)
	    else:
		val, message = footnote(ev, val, message, tag,
                                   "Maximum receiver window (%dk) is too small\n"%i)
		di_box(s, "bx_target", "fail peerMaxRwin val="+str(i))

        elif crwin < (mrwin - 2 * s["CurMSS"]): # current rwin is too small
            i = 100 * (mrwin - crwin) / mrwin;
            val, message = footnote(ev, val, message, "RWC",
                                    "Percent that the Receiver window has closed due to a receiver (cpu?) bottleneck\n", i)
	    di_box(s, "bx_target", "fail peerCloseRwin");
	else:
	    # triage rwnd indicated some otherwise unknown problem
	    val, message = footnote(ev, val, message, "RT",
				    "Triage reported receiver bottleneck, but none observed\n")
	    di_box(s, "bx_target", "fail peerTriageRwin");
	    # XXX missing check for stretch ACKs
	    exceptional = exceptional or transient

    # check sender limited
    # note that for future control mechanisms to limit transmissions
    # this may give incorrect results.  However since the current
    # controller sets cwnd and/or CwndLim, this test only reports
    # cases where the application fails to provide sufficient
    # data.
    i = s["SndLimTimeSender"]
    if i:
	pct = 100.0 * i / triagetotal
	# ignore transient (less than 1%) sender stalls
	if pct > 1.0:
	    val, message = footnote(ev, val, message, "SD",
                                "Percent time that the sending application has insufficient data to send (due to CPU limits?)\n",
                                pct)
	    di_box(s, "bx_tester", "warning testerBottleneck")

    # check interface back pressure
    i = s["SendStall"]
    if i:
        val, message = footnote(ev, val, message, "SS", "IPQ send stalled TCP\n", i)
	di_box(s, "bx_tester", "warning testerBottleneckNIC")

# the test below is usless on all but the shortest paths, and gives too many false alarms
#    if why and not val:
#        val, message = footnote(ev, val, message, "UNK",
#                                 "Failed to find non-congestion bottleneck(*)\n")
#	exceptional = exceptional or transient

# catchall MBZ tests, these should be replaced by explicit messages
    val, message = di_mbz(ev, val, message, s, mbzCC) # congestion control events
    val, message = di_mbz(ev, val, message, s, mbzRP) # data on the reverse path

# Diagnostic consistency checks

    # We depend on the kernel accurately reporting the window in packets
    if (s["obswinpkts"] * s["CurMSS"] != s["obswin"]):
        val, message = footnote(ev, val, message, "OW",
             "obswin is not an integral number of packets\n", s["obswin"])
	di_box(s, "bx_diag", "fail testerFractionalWindow obswin=%d mss=%d"%(s["obswin"],s["CurMSS"]))

    # Check for failing burst mode
    if s["burstwin"] and s["SSbursts"] == 0 or not s["burstwin"] and s["SSbursts"] != 0:
        val, message = footnote(ev, val, message, "BF",
             "Burst mode failure\n")
	di_box(s, "bx_diag", "fail testerBurstFailed")

    # let others know via ev["throttle"], ev["choke"], ev["punt"] if these seem to be show stoppers
    if val:
	ev["throttle"]=True

    # we are not lagging if awnd is still rising
    if not "maxawnd" in ev:
	ev["maxawnd"] = s["awnd"]
    pred = (s["win"] == 0 or s["win"] > s["awnd"]) and s["awnd"] <= ev["maxawnd"]
    if history(pred, ev, "lagging", 2):
	ev["choke"] = s
    if s["awnd"] > ev["maxawnd"]:
	ev["maxawnd"] = s["awnd"]

    # How long since last rtt measurment?
    if s["duration"] < 1000000:
	limit=3
    else:
	limit=1
    if history(s["CountRTT"]==0, ev, "stalled", limit):
	ev["punt"] = s

    head = " Others"
    s["di_other"] = (head, val, message)

# di_all - Figure out what happened
def di_all(s, ev, vl=None):
    """
    The main per sample diagnostic checks

    This performs a whole suite of checks on web100 TCP instruments to try to
    determine what might be limiting performance.  It assumes that the tester
    is deliberately limiting data transmissions for diagnostic reasons (so
    some sender limitations are not reported).  It tries to fully diagnose
    receiver (rwin) limitations and give some indications of the nature of
    path problems (e.g. distinguish between loss and reordering, etc).
    """
    # check for running out of time
    if "maxtime" in s and not "punt" in ev:
	ev["punt"] = True
	pp.runlog("E", "Exceeded running time limit")
    di_stats(s, ev)
#    if s["flag"] == 0:
#	if vl:
#	    dd_report(s, ev, ["di_stats"])  # other reports are likely to be invalid
#	return
    di_laminar(s, ev)
    di_other(s, ev)
    if vl:
	di_pf(s, ev)
	dd_report(s, ev, vl)

rowcount = 0
def di_prescan(ev, r, vl=None):
    """
    Rescan saved snaps to reconstruct a run
    """
    global rowcount
    n, o = None, None
    for d in r:
	c, n, o = d["tctrl"], d["rawsnap"], n
	if (not "win" in d):
	    d.update(pp.mkdict(c, n, o))
	    d["row"] = rowcount
	    rowcount += 1
	if o:
	    di_stats(d, ev)
    if o == None:
	pp.runlog("F", "Empty data set\n")
	sys.exit(3)

def rescan(ev, r, vl=None):
    """
    Diagnose all (di_all()) to reconstruct a run
    """
    for d in r:
	# exclude the zeroth sample, if there are no deltas
	if "ThruBytesAcked" in d:
	    di_all(d, ev, vl)

def fastrescan(ev, r):
    """
    Rerun di_laminar() on previous results
    """
    di_resetloss(ev, ev["maxpower"]["awnd"])
    for d in r:
	# exclude the zeroth sample, if there are no deltas
	if "ThruBytesAcked" in d:
	    di_laminar(d, ev)
################################################################
# Raw data collection and path measurment
################################################################
def prescan(opts, ev):
    """
    Get some baseline information about the path section, using
    native congestion control.  (Hopefully a slowstart).
    Idealy we want to know the following things:
    - Base (minimum) RTT
    - Approximate pipe size
    - Some gage of acceptable burst size (FUTURE)
    """
    # get path segment RTT and MSS
    pp.gctrl = pp.tctrl()
    pp.init_elapsed_sample(pp.gctrl.copy()) # zero'th sample has blank ctrl info
    
    pp.gctrl.basemss = cvar.baseMSS
    pp.gctrl.win = 0	# slowstart/ unconstrained CC
    pp.gctrl.duration =  OneSec
    pp.gctrl.flag = 1
    for i in range(0, 3):	# no more than 3 seconds
	ctrl = pp.gctrl.copy()
	r = pp.run_elapsed_sample(ctrl) # beware: alters ctrl
	di_all(r, ev, dd_verbosity())
	# quit once we are out of slowstart, or it stops opening the window
	if r["CongestionSignals"] or "choke" in r:
	    break

    # check for somethign dreadfully wrong
    if r["CountRTT"] <= 0:
        pp.runlog("E","It seems as though the data connection is not really running (Zero RTT)")
	sys.exit(5)

    ev["seg_pipe"]=ev["maxawnd"]
    ev["seg_rtt"] = 1.0*r["SumRTT"]/r["CountRTT"]	# this may include queues (slowstart)
    ev["min_rtt"] = r["MinRTT"]				# RTT in ms (float)

    # check for MTU discovery and various MSS foolishness
    # note that later MTU changes are likely to be fatal
    curMss = r["CurMSS"]
    if curMss != cvar.baseMSS:
	pp.runlog("W", "MSS change from %d to %d"%(cvar.baseMSS, curMss))
	cvar.baseMSS = curMss

    # now that we have the mss we can compute the runlen
    setTarget_runlen(ev, curMss)

    if opts.verbose:
	pp.runlog("I", "CID=%d, baseMSS=%d seg_rtt=%f"% (pp.cid, cvar.baseMSS, ev["seg_rtt"] ))
    # punt now if there is a problem with the system
    return([r])

def setuptest(ev, opts):
    """ Choose test parameters, based on path parameters and opts."""

    # a heuristic to estimate rounded test parameters, with weak precursor data
    global minpackets, maxpackets
    minpackets = opts.minpackets	# 3 unless explicitly requested
    maxpackets = opts.maxpackets	# 0 unless explicitly requested

    queuesize = ( 1000 / 8) * ev["target_rate"] * ev["target_rtt"]
    pipesize = ev["seg_pipe"]					# measured from slowstart, very noisy
    peakwin = queuesize + pipesize				# bytes, but just a guess
    peakpkts = peakwin/pp.cvar.baseMSS + 1			# a guess at peak packets
#    peakwin = 2*pipesize

    # pick a reasonable step size
    if opts.stepsize:
	s = opts.stepsize
    elif maxpackets:
	s = maxpackets/4
#    elif 1000 > ev["min_rtt"]*peakpkts/2: # The smaller of the next 2, w/o DIVZERO
    elif 1 > ev["min_rtt"]*peakpkts/2: # Suppresed except for  ev["min_rtt"] < 2
	s = peakpkts/2	# half of the predicted peak window
	pp.runlog("I", "Parameters based on %d pkts estimated peak window"%(peakpkts))
    else:
	s = int(1000/ev["min_rtt"]) # no extra settling time per coarse scan step
	pp.runlog("I", "Parameters based on %d ms initial RTT"%(int(ev["min_rtt"])))
    # make step size a power of 2, rounded down
    stepsize=1
    while stepsize<=s:
	stepsize = stepsize*2
    if stepsize > 1:
	stepsize = stepsize/2
    ev["stepsize"] = stepsize

    # minpackets has to be sane
    if minpackets<1:
	minpackets=1

    # pick max packets a multiple of stepsize above minpackets
    if maxpackets:
	maxpackets = minpackets + int(maxpackets/stepsize)*stepsize
    else:
        maxpackets = minpackets + 10*stepsize	# default to a 10 second coarse scan

    # explain the test
    pp.runlog("I", "peakwin=%d minpackets=%d maxpackets=%d stepsize=%d"%\
	      (peakwin, minpackets, maxpackets, stepsize))
    pp.runlog("I", "Target run length is %s packets (or a loss rate of %10.8f%%)"%\
	      (ev["target_runlen"], 100.0/ev["target_runlen"]))
    if opts.verbose:
	pp.runlog("I", "To repeat this test rerun with: -s %d -m %d -M %d"%\
		  (stepsize, minpackets, maxpackets))

def coarsescan(ev, result):
    """
    A "quick" scan the complete operating region
    """
    di_resetloss(ev)

    ss = ev["stepsize"]

    # Pass1: The initial scan of the entire space
    # XXXX need a smarter scanner here
    range=maxpackets-minpackets
    showpass(1, range/ss+1, "Coarse Scan")
    di_resetscan(ev)
    result.extend(doscan45(ev, minpackets, maxpackets, ss, fg=10))
    while not "choke" in ev:
        showpass(1, range/ss+1, "Coarse Scan")
        last=result[-1]
	result.extend(doscan45(ev, last["win"]+ss, last["win"]+maxpackets, ss, fg=11))
    return

priorpass = 0
subpass = 0
oldmess = ""
def showpass(n, s, m=""):
    global subpass, priorpass, oldmess
    if m == oldmess:
	m="..."
    else:
	oldmess=m
    if n == priorpass:
	subpass+=1
    else:
	subpass=0
	priorpass=n
    if subpass>25:
	subpass=0
    sp = "abcdefghijklmnopqrstuvwxyz"[subpass]
    t = s*options.duration # XXX out of scope
    pp.runlog("I", "Test %d%c (%d seconds): %s"%(n, sp, t, m))
    sys.stdout.flush()

def autoscan(ev, result):

    # Pass 2: hone in on the powerpoint
    # XXX this could be done with a convergent scanner
    ss = ev["stepsize"]
    if ss == 1:
	ss = 2
    di_resetscan(ev)
    while ss > 1:
	os = ss
	ss = ss/4
	if ss < 3:
	    ss = 1
        pw = ev["maxpower"]["awnd"]	# ignore chokes
	showpass(2, 2*os/ss+1, "Search for the knee")
        low=pw-os
        if low<3: low=3
	result.extend(doscan45(ev, low, pw+os, ss, fg=20))
    ev["scan_powerpoint"] = result[-1]

    # rescan to get total uncongested loss stats up to this point
    # No preconditions
    # XXX also need "maxlossless"
    fastrescan(ev, result)
    
    # Pass 2, duplex check if best window is 4 or smaller
    di_resetscan(ev)
    if ev["maxrate"]["awnd"] <= 4 :
	showpass(2, 10, "Duplex test")
	result.extend(doscan45(ev, 3, 10, 1, fg=21))  # test awnd=(3..10)
	ev["scan_duplex"] = result[-1]
    else:
	ev["gate_duplex"] = "maxrate %s"%ev["maxrate"]["awnd"]

    # Pass 3: hone in on standing queue overflow w/a laminar flow
    os = ss = ev["stepsize"]
    while not "punt" in ev and ss > 1:
        ml = ev["maxlaminar"]["awnd"]   # scan from previous high window
	# if the last point was the peak, don't reduce step size
	if ev["maxlaminar"] != result[-1]:
	    os = ss
	    ss = ss/4
	    if ss < 3:
		ss = 1
	showpass(3, 2*os/ss+1, "Measure static queue space")
	low=ml-os
	if low<minpackets:
	    low=minpackets
	di_resetscan(ev)
	result.extend(doscan45(ev, low, ml+os, ss, fg=30))
    ev["scan_static"] = result[-1] # mark the end

    # Future Pass 3a: measure qsize w/ line rate bursts
    # XXX omitted

    # Pass 4: make sure we have enough data to measure the loss rate
    if  ev["lossCS"] >= 4:
	pp.runlog("I", "Already have sufficient loss data")
    else:
	samp = 10				# 10 seconds at a time
	limit = int(ev["target_runtime"]/500) + 10	# twice AMID cycle time for target path plus fudge 
	# XXXX check for limit > maxtime-time.time()
	limit = (int(limit/samp)+1)*samp		# round up
	pp.runlog("I", "Accumulate loss statistics, no more than %d seconds:"%limit)
    	if 2*ev["maxpower"]["rate"]<ev["target_rate"]:
	    pp.runlog("I", "(Data rate may be too low to collect full loss statistics)")
	    ev["gate_loss"]="rate %s"%ev["maxpower"]["rate"] # but not really gated
    	# collect some data, 10 seconds at a time
    	mpwindow = ev["maxpower"]["awnd"]
    	while not "punt" in ev and ev["lossCS"] < 4 and limit > 0:
	    showpass(4, samp, "Accumulate loss statistics")
	    result.extend(doscan45(ev, mpwindow, mpwindow, 1, samp*pp.OneSec, fg=40))
	    limit = limit - samp
    ev["scan_loss"] = result[-1] # mark the end

    fastrescan(ev, result)
    return

# doscan0 - setup and quit
# doscan1 - 1d scan of window size, with stabilization
def doscan01(ev, low, high, step, fg=1):
    if options.verbose:
        dd_showhead()
    result = []
    for win in range(low, high+1, step):
        # stabilize at new window
        pp.gctrl.flag = 0
        pp.gctrl.win = win
        pp.gctrl.burstwin = 0
        pp.gctrl.duration = pp.OneSec
        ctrl = pp.gctrl.copy()
        r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
        result.append(r)
        di_all(r, ev)
        if options.scan == 0:
            return (result)	# punt after stabilizing the connection

        pp.gctrl.flag = fg
        pp.gctrl.duration = duration
        ctrl = pp.gctrl.copy()
        r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
        result.append(r)
        di_all(r, ev, dd_verbosity())
    return (result)

# doscan2 - 2d scan of window and burst parameter space, with stabilization
# doscan3 - 1d scan of left edge of window and burst parameter space, with stabilization
def doscan23(ev, low, high, step, fg=1):
    if options.verbose:
        dd_showhead()
    result = []
    for win in range(low, high+1, step):
        # stabilize at new window
        pp.gctrl.flag = 0
        pp.gctrl.win = win
        pp.gctrl.burstwin = 0
        pp.gctrl.duration = pp.OneSec
        ctrl = pp.gctrl.copy()
        r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
        result.append(r)
        di_all(r, ev)

        pp.gctrl.flag = fg
        pp.gctrl.duration = duration
        top = win-1
        if (options.scan == 3 and win != high):
            top = 1		# XXX old calling sequence?
        for burst in range(0, top, step):
            pp.gctrl.burstwin = burst
            ctrl = pp.gctrl.copy()
            r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
            result.append(r)
            di_all(r, ev, dd_verbosity())
    return (result)

# doscan4 - 1d scan of window, no stabilization
# doscan5 - 1d scan of burst, no stabilization
def doscan45(ev, low, high, step, dur=0, fg=1):
    if dur==0:
	dur=duration
    result = []
    pp.gctrl.flag = 0
    pp.gctrl.win = low
    pp.gctrl.burstwin = 0
    pp.gctrl.duration = pp.OneSec
    ctrl = pp.gctrl.copy()
    # XXX need to loop if awnd > low
    r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
    di_all(r, ev)
    result.append(r)
    pp.gctrl.flag = fg
    pp.gctrl.duration = dur
    for win in range(low, high+1, step):

        # Go to the new window or burst
        pp.gctrl.win = win
        if options.scan == 5:
	        pp.gctrl.burstwin = win - low
        ctrl = pp.gctrl.copy()
        r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
        di_all(r, ev, dd_verbosity())
        result.append(r)
	if "choke" in ev or "punt" in ev:
	    break
    return (result)

# doforever - load a path at a fixed rate
def doforever(ev):
    global maxpackets 

    # copied from setuptest()
    maxpackets = options.maxpackets	# XXX scope
    rtt = ev["target_rtt"]
    if ev["seg_rtt"] < rtt:
	rtt = int(ev["seg_rtt"])+1
    pipesize = ( 1000 / 8) * ev["target_rate"] * rtt     # bytes
    if maxpackets:
        win = maxpackets
    else:
        win = (pipesize+pp.cvar.baseMSS-1)/pp.cvar.baseMSS
    print "Selected window size (packets):", win
    ev["target_runlen"] = win+1

    dd_showhead()

    while not "choke" in ev:
	# run with the chosen window
        pp.gctrl.flag = 0
        pp.gctrl.win = win
        pp.gctrl.burstwin = 0
        pp.gctrl.duration = duration
        ctrl = pp.gctrl.copy()
        r=pp.run_elapsed_sample(ctrl) # beware: alters ctrl, pp.ns, pp.os
        di_all(r, ev, dd_verbosity())

	# trim the window and decide if we are done here

    return (0)

################################################################
# System wide tester checks
################################################################
def getproc(name, count=1):
    """
    Read a small number of lines from a configuration file
    and return them as a list.

    As a special case, if we read exactly 1 line (the default),
    return the line itself (not a list).
    """    
    try:
	pfile=open(name, "r")
	ret=pfile.readlines()
	pfile.close()
    except:
	return(None)
    if count == 1:
	return(ret[0].strip())
    return(ret[:count])

################################################################
# Per run logic: option parsing and the main
################################################################

umsg = """For path diagnosis:
%prog [-v] -H hostname RTT target-rate
    The required arguments are:
        RTT         - Estimated RTT to the target          in msec
        target-rate - Target bandwidth                     in Mbps

For experts:
%prog [run-options] host-option RTT target-rate
    One host-option (-Hhost, -Ccid, -Ffd or -L) is required
or alternate form for reprocessing logged data:
    %prog -R -l logbase [-vv] [var or report name(s)]"""

def usage(msg=None):
    if msg:
        pp.runlog("E", "Error %s"%(msg))
    pp.runlog("E", "Use -h for help")
    sys.exit(1)

stepsize = 0
duration = 0
exceptional = False
transient = False  # If transient is false, undiagnosed transient events are ignored
# unless they happen to "maxrate", etc
# If transeint is true they are all reported as exceptional

def getcmdline(ev):
    """ Parse command line arguments """

    global options, exitcode

    parser = OptionParser(usage=umsg)

    pp.setupParse(parser)

    parser.add_option("-D", "--duration",
	help="Sample duration in sec",
	type="int", default=1, dest="duration")
    parser.add_option("-f", "--forever",
	help="Loop forever at target rate",
	action="store_true", dest="foreverf")
    parser.add_option("-s", "--step",
	help="Initial step size (must be a power of 2)",
	type="int", default=0, dest="stepsize")
    parser.add_option("-S", "--scan",
	help="Scan pattern: 1(1d), 2(2d), 3(Left edge)",
	type="int", default=-1, dest="scan")
    parser.add_option("-m", "--minpackets",
	help="Min window size in packets",
	type="int", default=3, dest="minpackets")
    parser.add_option("-M", "--maxpackets",
	help="Max window size in packets",
	type="int", default=0, dest="maxpackets")
    parser.add_option("", "--maxwindow",
	help="Max window size in bytes",
	type="int", default=0, dest="maxwindow")
    parser.add_option("-v", "--verbose",
	help="Raises the verbosity, also -v -v, etc",
	action="count", default=0, dest="verbose")
    parser.add_option("-R", "--reprocess",
	help="Reprocess saved test results",
	action="store_true", default=False, dest="replot")
    parser.add_option("-l", "--log",
	help="Base name for the log/replay files",
	default="temp", dest="logbase")
    parser.add_option("-r", "--rate",
	help="Override rate (for reprocessing logs)",
	type="int", default=0, dest="rate")
    parser.add_option("-t", "--RTT",
	help="Override RTT (for reprocessing logs)",
	type="int", default=0, dest="rtt")
    parser.add_option("", "--format",
	type="string", default="x")
    parser.add_option("", "--plot",
	type="string", default=None)

    options, args = parser.parse_args()
    pp.setupRunlog(options, options.format[0]) # XXXX

    global maxpackets

    if options.replot:
	doredo(ev, options, args)

    global duration
    duration = options.duration	* pp.OneSec
    ev["target_rate"] = options.rate
    ev["target_rtt"] = options.rtt

    if len(args) == 2:
	ev["target_rtt"] = int(args[0])
	ev["target_rate"] = int(args[1])
    if ev["target_rate"] <= 0 or ev["target_rtt"] <= 0:
    	usage("missing or incorrect RTT and target rate")
    # can redefine args

################
# Exit codes (to faclilitate scripting)

# small intergers reflect fatal/immedate exits
# 0 - Passed everything
# 1 - Misc/unknown error (including python errors)
# 2 - (Future) improper arguments
# 3 - Reading from an empty or truncated log file.
# 4 - send forever exited
# 5 - path or data connection fails parameter consistencey checks


# bitwise combinations summarize test results
exitcode = 0
def setexit_rescan():		# Insufficient data for rescan
    global exitcode
    exitcode = exitcode | 8
def setexit_path():		# Bottleneck in the path
    global exitcode
    exitcode = exitcode | 16
def setexit_receiver():		# Bottleneck in the receiver
    global exitcode
    exitcode = exitcode | 32
def setexit_sender():		# Bottleneck in the sender/tester
    global exitcode
    exitcode = exitcode | 64
def setexit_unknown():		# Undiagnosed event or incomplete report
    global exitcode
    exitcode = exitcode | 128

def doredo(ev, opts, args):
    oldev, result=pp.read_stats(opts.logbase)
    ev["orig_ev"] = oldev

    # first scan: precompute all per row stats, maxpower, maxlaminar, etc
    di_prescan(ev, result)		# precompute most events
    for i in oldev:			# port all other events
	if not i in ev:
	    ev[i] = oldev[i]
    # remove footlist to force new messages
    if "footlist" in ev:
	del ev["footlist"]
    # reconstruct some events missing from older traces
    try:
	r0, r1, r2 = result[0], result[1], result[2]
	if not "stepsize" in ev:
	    ev["stepsize"] = r2["win"]-r1["win"]
	if not "seg_rtt" in ev:
	    ev["seg_rtt"] = 1.0*r1["SumRTT"]/r1["CountRTT"]
	if not "version_pathdiag" in ev:
	    ev["version_pathdiag"]="Unknown, prior to May 2005"
	rescan(ev, result) # reconstruct everything else
    except Exception, e:
	    print "Truncated or malformed log file"
	    sys.exit(3)

    rsflag="orig"			# origional parameters
    if opts.rate:
	ev["orig_target_rate"]=ev["target_rate"]
	ev["target_rate"]=opts.rate
	rsflag="different"
    if opts.rtt:
	ev["orig_target_rtt"]=ev["target_rtt"]
	ev["target_rtt"]=opts.rtt
	rsflag="different"
    setTarget_runlen(ev, result[-1]["CurMSS"])
	
    if opts.verbose:
	dd_showhead()
	fmt=["di_stats", "di_PF", "di_laminar" ]
	if args:
	    fmt.extend(args)
	fmt.append("di_other")
    else:
	fmt=None
    ev["rescan"] = rsflag		# how to report insufficient data

#    rescan(ev, result)
    di_resetloss(ev, ev["maxpower"]["awnd"])
    rescan(ev, result, fmt)
    page=dd_user(ev, result)
    dd_emitreport(ev, page, opts)
#    pp.write_events(ev, sys.stdout)
    if opts.verbose > 2:
	print "Diff events"
	pp.diff_events(ev, oldev, sys.stdout)
    sys.exit(exitcode)

def main():
    """
    Process switches and choreograph the testing
    """
    global options, maxpackets, exitcode
    gev={}
    getcmdline(gev)
    if options.verbose:
	dd_showhead()

    di_resetloss(gev)
    pp.setupTCP(gev, options)
    # get minimal information about the section
    result = prescan(options, gev)
    if options.foreverf:
	doforever()
	sys.exit(4)	# somethign went wrong
    else:

	setuptest(gev, options)
	pp.pretuneTCP(options)	# XXX fold into setupTCP()
	if options.scan == -1:
	    if not dd_checksys(gev, options): # confirm maximum server size
		coarsescan(gev, result)
		autoscan(gev, result)
	    else:
		coarsescan(gev, result) # just get the basics and quit
	    fastrescan(gev, result)	# normalize results before writing
	    pp.write_stats(gev, options.logbase)
	    page=dd_user(gev, pp.allRuns) # XXX allRuns?
	    dd_emitreport(gev, page, options, True)
	    sys.exit(exitcode)
	elif options.scan == 0 or options.scan == 1:
	        result=doscan01(gev, minpackets, maxpackets, stepsize)
	elif options.scan == 1 or options.scan == 3:
		result=doscan23(gev, minpackets, maxpackets, stepsize)
	elif options.scan == 4 or options.scan == 5:
		result=doscan45(gev, minpackets, maxpackets, stepsize)
	else:
		raise "Unknown scan parameter"
	pp.write_stats(gev, options.logbase)
	sys.exit(exitcode)

# doit - has to be last
# print ("check version 3")
if __name__ == '__main__': main()
