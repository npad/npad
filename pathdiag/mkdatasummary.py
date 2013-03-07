#!/usr/bin/env python

import glob
import os
import sys
import time

TMPFILE="_summary.html"
OUTFILE="summary.html"

def main():
	if len(sys.argv) > 1:
		os.chdir(sys.argv[1])
	
	# Fix legacy dirnames
	for dir in glob.glob("OldReports*/"):
		os.rename(dir, dir[3:])
		
#	# Fix legacy files without per month dirs
#	for report in glob.glob("*smry.html"):
#		prefix = report[:report.index("smry.html")]
#		month = (report[report.index(":")+1:])[:7]
#		dirname = "Reports-%s"%month
#		try:
#			os.mkdir(dirname)
#		except OSError, e:
#			if e[0] != 17:
#				raise e
#		for filename in (glob.glob("%s*"%prefix)):
#			os.rename(filename, "%s/%s"%(dirname, filename))

	# Add required help as needed, adjusting parent URLs
	f = open("help.html")
	for dir in glob.glob("Reports*/"):
		nhelp="%shelp.html"%dir
		if not  glob.glob(nhelp):
			f.seek(0)
			fo = open(nhelp, 'w')
			for line in f:
				fo.write(line.replace("..", "../.."))
			fo.close()
	f.close()	

	# Add required css as needed
	f = open("boxes.css")
	for dir in glob.glob("Reports*/"):
		ncss="%sboxes.css"%dir
		if not  glob.glob(ncss):
			f.seek(0)
			fo = open(ncss, 'w')
			for line in f:
				fo.write(line)
			fo.close()
	f.close()	
	
	#
	# Generate summary
	#
	t = time.gmtime()
	m1 = t.tm_mon
	y1 = t.tm_year
	m2 = ((m1 - 2) % 12) + 1
	if m2 > m1:
		y2 = y1 - 1
	else:
		y2 = y1
	filenames = (glob.glob("Reports-%04d-%02d/*smry.html"%(y1, m1)))
	filenames.extend(glob.glob("Reports-%04d-%02d/*smry.html"%(y2, m2)))
	filenames.sort()
	filenames.reverse()
	hosts = {}
	for filename in filenames:
		hostname = filename[filename.index("/")+1:]
		hostname = hostname[:hostname.index("-")]
		if hostname[-5:] == ":2012":		# new filename syntax version shim
			hostname = hostname[:-5]
		try:
			hosts[hostname]
		except:
			hosts[hostname] = []
		hosts[hostname].append(filename[:filename.index("smry.html")])

	outfile = file(TMPFILE, "w")
	outfile.write(""" <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2//EN">
<html><head>
<title>Result Table</title>
<link rel="stylesheet" href="boxes.css" type="text/css" />
</head><body>
  <h1>Result Table</h1>
<p>Back to the
 [Result Table]
 <a href="http://www.psc.edu/networking/projects/pathdiag/">[General documentation]</a>
<a href="../">[Server Form]</a>
<p>&nbsp;
<table border="1" bordercolor="#CCCCCC" cellspacing="0">
<tr>
  <th>Parameters</th>
  <th>End-System Tests</th>
  <th>Path Tests</th>
  <th>Tester</th>
</tr>
""")

	items = hosts.items()
	items.sort()
	for (hostname, reports) in items:
		outfile.write("""<tr>
<td bgcolor="#C0C0FF" colspan="4"><a name="%s" href="#%s">%s</a></td>
</tr>"""%(hostname, hostname, hostname))
		for report in reports:
			(dir, f) = report.split("/")
			infile = open(report+"smry.html", "r")
			outfile.write(infile.read().replace('"./%s.html"'%f, '"./%s.html"'%report)) # fix smry URLs
			infile.close()

	outfile.write("</table></body></html>\n")
	outfile.close()

	os.rename(TMPFILE, OUTFILE)

if __name__ == '__main__': main()
