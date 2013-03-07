CFLAGS = -Wall -O -g

EXEC_FILES = *.py
WWW_FILES = DiagClient.jar diag-client.c

all: DiagClient.jar diag-client

DiagClient.jar: DiagClient.java
	javac -source 1.3 DiagClient.java
	jar cf DiagClient.jar *.class

diag_client: diag-client.o

#DiagServer.pyc: DiagServer.py DiagServerConfig.py Traffic.py
#	python -c 'import DiagServer'

# note that findbugs produces no output file - it just writes to sysout
findbugs: DiagClient.jar
	findbugs -textui DiagClient.jar

clean:
	rm -f *.pyc *.o diag-client

veryclean:
	rm -f *.class *.jar *.pyc *.o diag-client

-include ../Makefile.config

install:
	@if [ -z "$(EXEC_DIR)" ]; then \
		echo "You need to run the config script before installing."; \
		echo "See the INSTALL document in the distribution for more information."; \
		exit 1; \
	fi
	@for file in $(EXEC_FILES); do \
		rm -f $(EXEC_DIR)/$file; \
	done
	cp $(EXEC_FILES) $(EXEC_DIR)
	@for file in $(WWW_FILES); do \
		rm -f $(WWW_DIR)/$file; \
	done
	cp $(WWW_FILES) $(WWW_DIR)
