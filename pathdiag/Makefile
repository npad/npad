TARGETS    = _pathlib.so help.html
SWIG       = swig
PYINCLUDE  = -I`python -c 'import sys; print("%s/include/python%s"%(sys.prefix, sys.version[:3]))'`
# BEWARE: -fpic not needed or not correct with all compilers
PICFLAG    = -fpic
DYNLINK    = ld -shared -t
EXEC_FILES = pathdiag.py* pathtools.py* prettyhtml.py* pathlib.py* _pathlib.so mkdatasummary.py *.fmt
LOGDIR_FILES = boxes.css help.html

-include ../Makefile.config

ifndef WC_PREFIX
WC_PREFIX = /usr/local
endif
PYTHONPATH = $(WC_PREFIX)/lib/python`python -c 'import sys; print(sys.version[:3])'`/site-packages

all:  $(TARGETS)

# the help file
help.html: prettyhtml.py default.fmt
	./prettyhtml.py

# The C part of the diagnostic
pathlib.o: pathlib.c pathlib.h
	$(CC) -g -I$(WC_PREFIX)/include -c $(PICFLAG) pathlib.c -o pathlib.o

# BEWARE: We break apart the swig compile so we can ship intermediate files
# for instalation without installing swig.
# If you get errors that might be "c" wrapper compatibility problems
# (missmatched types, etc), either get swig and do 'make makeswig'
# or you can try different versions of the saved swig code.
# (if you change SAVESWIG you need to make clean; make)

# For python 2.5 w/ swig 1.3.31 (may be an exception):
# SAVESWIG=swigout1331
# For python 2.4 and most contemporary swig's:
SAVESWIG=swigout
# For python 2.3
# SAVESWIG=swig-for-python2.3:

SWIGOUT=pathlib.py pathlib_wrap.c
makeswig:
	$(SWIG) -python -I$(WC_PREFIX)/include pathlib.i

saveswig: makeswig
	mkdir -p $(SAVESWIG)
	cp $(SWIGOUT) $(SAVESWIG)

noswig:
	rm -f $(SWIGOUT)
	cp $(SAVESWIG)/pathlib.py .
	cp $(SAVESWIG)/pathlib_wrap.c .

# beware: make recursion 
pathlib.py pathlib_wrap.c: pathlib.i pathlib.h
	make noswig

_pathlib.so: pathlib_wrap.c pathlib.o
	$(CC) -g $(PYINCLUDE) -DSWIG_PYTHON_SILENT_MEMLEAK -I$(WC_PREFIX)/include -fno-stack-protector -c $(PICFLAG) pathlib_wrap.c
	$(DYNLINK) -o _pathlib.so pathlib_wrap.o pathlib.o -rpath $(WC_PREFIX)/lib -L$(WC_PREFIX)/lib -lweb100

clean:
	rm -f *.o *.so *.pyc pathlib.py temp* *_wrap.c $(TARGETS)

install:
	@if [ -z "$(EXEC_DIR)" ]; then \
		echo "You need to run the config script before installing."; \
		echo "See the INSTALL document in the distribution for more information."; \
		exit 1; \
	fi
	@for file in $(EXEC_FILES); do \
		rm -f $(EXEC_DIR)/$$file; \
	done
	cp $(EXEC_FILES) $(EXEC_DIR)
	@for file in $(LOGDIR_FILES); do \
		rm -f $(LOGDIR)/$file; \
	done
	cp $(LOGDIR_FILES) $(LOGDIR)
	
#	@echo -ne "\nRegenerating reports.  This may take several minutes if you have a lot of reports..."
#	@( cd $(LOGDIR); \
#	export PYTHONPATH=$(PYTHONPATH); \
#	for f in *.ctrl; do \
#		f=`basename $$f .ctrl`; \
#	   	if [ -f $$f.ctrl -a -f $$f.log ]; then \
#			$(EXEC_DIR)/pathdiag.py -R --format=tth -l $$f || true; \
#		fi; \
#	   done; )
	@echo -ne "\nRegenerating report summary..."
	@( cd $(LOGDIR); $(EXEC_DIR)/mkdatasummary.py )
	@echo -ne "  Done.\n\n"
