#!/usr/bin/env python

import sys
import string

helplist = []
def getdefs(keyword, fname):
    tag = ""
    list = {}
    sfile=open(sys.path[0]+"/"+fname, "r")
    for line in sfile:
	line=line.rstrip()
	if len(line) == 0:
	    tag= ""
	    continue
	if line[0] == "#": continue
	sl = line.split()
	if sl[0] == keyword:
	    tag = sl[1]
	    list[tag]=[]
	    if keyword == "helptag" and tag != "X":
		helplist.append(tag)
	    continue
	if tag:
	    list[tag].append(line)
    return list

def getformats(fname):
    flist = getdefs("fmt", fname)
    if not "DefFormat" in flist:
	flist["DefFormat"]=[]
	flist["DefFormat"].append("No format [format] XXX")
	flist["DefFormat"].append("[message]")
    return flist

def getmessages(fname):
    return (getdefs("tag", fname))

def gethelp(fname):
    return (getdefs("helptag", fname))

def message(ofile, m, flist, mlist, hlist=None):
    """
    Process a message string of the format:
    fmt keyword arg=val arg=val
    """
    botch=False

    # extract the format name
    try:
	alist=m.split(" ")
    except AttributeError:
	alist=m[:]
	botch=True
    fmt=alist[0]
    try:
	del alist[0]
    except:
	print "del failed", alist
    if fmt in flist:
	llist=flist[fmt]		# format (line) list
    else:
	llist=flist["DefFormat"]	# default format

    # extract the message name
    name="-"
    try:
	name=alist[0]
	del alist[0]		# argument list - look at print above if python punts
    except IndexError:
	pass

    # do the logic for the conditional help 
    help=""
    if hlist and name in hlist and "helpfmt" in flist:
	help=" ".join(flist["helpfmt"])	# flist is an array of strings

    # Prep the arguments
    alist.extend(["help="+help, "format="+fmt, "name="+name, "pathdiag=http://www.psc.edu/networking/projects/pathdiag/"])

#    if botch: print "XXX>", fmt, name, alist
    if name in mlist and not mlist[name]:
	return			# ignore defined empty messages
    for line in llist:
	if line == "[message]":
	    if not name in mlist:
		ofile.write("Message >%s<: not found XXX\n"%(name))
		return
	    llist=mlist[name]	# message (line) list
	    for line in llist:
		ofile.write(subargs(line, alist)+"\n")
	else:
	    ofile.write(subargs(line, alist)+"\n")

def subargs(line, alist):
    for w in alist:
	try:
	    vname, val = w.split("=", 1)
	    line = line.replace("["+vname+"]", val)
	except ValueError:
	    pass
    return line

################################################################
# tools for generating message lists
def boxstart():
    "Create a new (empty) box"
    return []
def boxmessage(bx, mess):
    "add a message to a box"
    bx.append(mess)
def boxpush(bx, arg):
    "insert messages at the top of a box"
    bx[0:0]=[arg]
def boxmerge(bx, bx2, dupcheck=False):
    """
    merge a box in to an outer scope box.  If dupcheck is true,
    avoid duplicating any messages.
    """
    if dupcheck:	# If checking dups, we do an explicit merge
	for item in bx2:
	    for i in bx:
		if item == i:
		    break
	    else:
		bx.append(item)
    else:	# if not checking dups, use the library
	bx.extend(bx2)
def _boxlist(bx):
    "Debugging only"
    for line in bx:
	print line
def boxhtml(ofile, bx, flist, mlist, hlist=None):
    "Output boxes in html"
    for line in bx:
	message(ofile, line, flist, mlist, hlist)

################################################################
def testmain():
    formats = getformats("test.fmt")
    messages = getmessages("test.fmt")

#    message("P LRpass lossrate=0.002 runlength=500", formats, messages)

    b0=boxstart()
    boxmessage(b0, "title Box0")

    b1=boxstart()
    boxmessage(b1, "title Box1")
    boxmessage(b1, "F line1 none")
    boxpush(b1, "openbox - type=fail")
    boxmessage(b1, "closebox")

    boxmerge(b0, b1)
    boxmessage(b0, "P line1 none")
    boxpush(b0, "openbox - type=pass")
    boxmessage(b0, "closebox")

    page=boxstart()
    boxmessage(page, "beginpage")
    boxmerge(page, b0)
    boxmessage(page, "endpage")
    ofile=open("foo.html", "w")
    boxhtml(page, formats, messages, ofile)
#    _boxlist(page)

def mkhelp(hname, fname):
    """Make a help file from a format file"""
    ofile = open(hname, "w")

    flist = getformats(fname)
    hlist = gethelp(fname)
    mlist = getmessages(fname)
    message(ofile, "BeginHelpPage -", flist, mlist)
    for htag in helplist:
	if htag not in mlist or string.find(mlist[htag][-1], "[help]") == -1:
	    print "Orphaned helptag:", htag
#	print htag
	message(ofile, "HelpTitle "+htag, flist, mlist)
	message(ofile, "HelpText "+htag, flist, hlist)
    message(ofile, "EndHelpPage -", flist, mlist)
    for htag in mlist:
	if string.find(mlist[htag][-1], "[help]") != -1 and htag not in hlist:
	    print "Missing help:", htag

# doit - has to be last
# if __name__ == '__main__': testmain()
if __name__ == '__main__':
    mkhelp("help.html", "default.fmt")
