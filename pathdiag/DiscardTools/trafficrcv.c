/*
 * trafficrcv.c Data sink for TCP transfer tests Jeffrey Semke, Matthew
 * Mathis, and Raghu Reddy Pittsburgh Supercomputing Center August 1999;
 * Revised on Mar 2002 
 */

/*
 * $Id: trafficrcv.c,v 1.3 2007/06/06 19:42:21 mathis Exp $ 
 */

/*
 * Thanks to Shirl Grant and John Heffner for their testing on FreeBSD and
 * Linux.  I have incorporated their patches to make this work on more than
 * just NetBSD.
 */

/*
 * On Solaris, build with: -lsocket -lnsl
 * On Tru64, build with: -D_XOPEN_SOURCE=500
 *
 * To use TCP Wrappers (libwrap), build with: -DLIBWRAP -lwrap
 */

#include <sys/types.h>		/* for FreeBSD */
#include <stdio.h>		/* for stderr */
#include <stdlib.h>		/* for random */
#include <sys/socket.h>		/* for socket, setsockopt, connect, etc */
#include <netinet/in.h>		/* for IPPROTO_TCP and name */
#include <arpa/inet.h>
#include <errno.h>		/* for errno */
#include <unistd.h>		/* for fork */
#include <sys/wait.h>		/* for waitpid */
#include <syslog.h>		/* for syslog */
#include <netdb.h>
#include <string.h>
#include <stdarg.h>
#include <signal.h>

#ifdef LIBWRAP
 #include <tcpd.h>
 int allow_severity = LOG_INFO;
 int deny_severity = LOG_WARNING;
#endif

#define DAEMON		"trafficrcv"
#define TPORT           56117		/* default port; use -p port to change */
#define APPBUF          (1024 * 1024)
#define BUF_STEPSIZE    1024

static void
usage(char name[])
{
    fprintf(stderr,
	    "Usage: %s [-p port] [-b sockbuf_bufsize | -B] [-c host]"
	    " [-t timeout] [-m max_clients] [-D] [sockbuf_size]\n", name);
}

static void
ttylog(int level, const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	if (level > LOG_WARNING) {
		vprintf(fmt, ap);
		fflush(stdout);
	} else
		vfprintf(stderr, fmt, ap);
	va_end(ap);
}

static void (*log)(int, const char *, ...) = ttylog;

static void
daemonize(void)
{
	log(LOG_INFO, "Daemonizing...\n");
	switch (fork()) {
	  case -1:
		log(LOG_CRIT, "Error forking daemon: %s\n", strerror(errno));
		exit(-1);
	  case 0:
		break;
	  default:
		exit(0);
	}

	if (setsid() < 0) {
		log(LOG_CRIT, "setsid failed: %s\n", strerror(errno));
		exit(-1);
	}
	openlog(DAEMON, LOG_PID, LOG_DAEMON);
	log = syslog;
	fclose(stdin);
	fclose(stdout);
	fclose(stderr);
}

/*
 * Poor man's semaphore (not requiring thread lib): we will up it only in the
 * signal handler, taking care not to re-enter.  We will down it only with the
 * signal blocked.  Inc and Dec should be atomic, but we'll be careful anyway.
 */
static int child_avail = -1;
static void
child_handler(int sig)
{
    int status;
    
    while (waitpid(-1, &status, WNOHANG) > 0) {
	if (WIFEXITED(status) || WIFSIGNALED(status)) child_avail++;
    }
}

static void
child_down(void)
{
	sigset_t chldset;

	sigemptyset(&chldset);
	sigaddset(&chldset, SIGCHLD);
	sigprocmask(SIG_BLOCK, &chldset, NULL);
	child_avail--;
	sigprocmask(SIG_UNBLOCK, &chldset, NULL);
}

static int alarmed;
static void
alarm_handler(int sig)
{
    alarmed = 1;
}

static int
finish(int sock)
{
    int             result;

    do {
	result = shutdown(sock, 2);
    } while ((result == -1) && (errno == EINTR));
    if (result == -1) {
	log(LOG_ERR, "Error closing connection: %s\n", strerror(errno));
	return -1;
    }

    return 0;
}

static int
read_until_close(int sock, int timeout)
{
    char           *databuf;
    int             bytes,
                    rbytes;
    struct sigaction sa;

    /*
     * Set up data buffer 
     */
    if ((databuf = malloc(APPBUF)) == NULL) {
	log(LOG_CRIT, "Malloc of data buffer failed\n");
	exit(-1);
    }

    /*
     * Receive data 
     */
    bytes = APPBUF;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = alarm_handler;
    if (sigaction(SIGALRM, &sa, NULL)) {
	log(LOG_CRIT, "sigaction for SIGALRM failed\n");
	exit(-1);
    }
    do {
	alarm(timeout);
	rbytes = read(sock, databuf, bytes);
	if (rbytes == -1) {
	    if (errno != EINTR) {
		log(LOG_ERR, "Recv: %s\n", strerror(errno));
		/*
		 * close socket and exit 
		 */
		finish(sock);
		return -1;
	    } else {
		rbytes = 1;	/* clear the error and read again */
	    }
	}
    } while (rbytes > 0 && !alarmed);

    /*
     * Close the connection 
     */
    return finish(sock);
}

int
main(int argc, char *argv[])
{
    socklen_t       opt_len;
    struct sockaddr_in name,
                    newname;
    socklen_t       newnamelen;
    long            bufsize = 0;	/* use default */
    long            bufsizea = 0;	/* actual bufsize */
    long            bufsizea2 = 0;
    int             result;
    int             sock,
                    newsock;
    pid_t           pid;
    int             port = TPORT;
    int             errflg = 0;
    char            host[256];
    int             client = 0;
    int             maxbuf = 0;
    int             timeout = 0;
    int             daemon = 0;

    int             c;

    while ((c = getopt(argc, argv, "h?p:b:Bc:t:Dm:")) != -1) {
	switch (c) {
	case 'h':
	case '?':
	    errflg++;
	    break;
	case 'p':
	    port = atoi(optarg);
	    break;
	case 'b':
	    if (maxbuf != 0)
	        errflg++;
	    bufsize = atoi(optarg);
	    break;
	case 'B':
	    if (bufsize != 0)
	        errflg++;
	    maxbuf = 1;
	    break;
	case 'c':
	    strncpy(host, optarg, 255);
	    host[255] = '\0';
	    client = 1;
	    break;
	case 't':
	    timeout = atoi(optarg);
	    break;
	case 'D':
	    daemon = 1;
	    break;
	case 'm':
	    child_avail = atoi(optarg);
	    break;
	default:
	    errflg++;
	    break;
	}
    }

    // For backword compatibility; bufsize given as an arg
    if (optind == argc - 1)
	bufsize = atoi(argv[optind]);

    if (errflg) {
	usage(argv[0]);
	exit(2);
    }

    /*
     * Create a socket to test with
     */

    if ((sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
	perror("Couldn't create a socket");
	exit(-1);
    }

    /*
     * Set the buffer size, if specified 
     */
    opt_len = sizeof(bufsize);

    if (bufsize) {
	if (setsockopt
	    (sock, SOL_SOCKET, SO_RCVBUF, (void *) &bufsize, opt_len)) {
	    perror("Couldn't set receive socket buffer size");
	    exit(-1);
	}
    } else if (maxbuf) {
	do {
	    bufsizea2 = bufsizea;
	    bufsize += BUF_STEPSIZE;
	    setsockopt(sock, SOL_SOCKET, SO_RCVBUF, (void *)&bufsize, opt_len);
	    if (getsockopt(sock, SOL_SOCKET, SO_RCVBUF, (void *)&bufsizea, &opt_len)) {
		perror("getsockopt");
		exit(-1);
	    }
	} while (bufsizea > bufsizea2);
    }
    if (getsockopt
	(sock, SOL_SOCKET, SO_RCVBUF, (void *) &bufsizea, &opt_len)) {
	perror("Couldn't get receive socket buffer size");
	exit(-1);
    }
    printf("Getsockopt() reports %ld byte socket buffers\n", bufsizea);

    if (client) {
        /*
         * We're a client.  Do active connect.
         */
        
	struct hostent *hent;

	if ((hent = gethostbyname(host)) == NULL) {
	    fprintf(stderr, "gethostbyname error\n");
	    exit(-1);
	}
	memset(&name, 0, sizeof(name));
	name.sin_family = AF_INET;
	memcpy(&name.sin_addr, hent->h_addr_list[0], 4);
	name.sin_port = htons(port);

	if (connect(sock, (struct sockaddr *) &name, sizeof(name)) != 0) {
	    perror("connect");
	    exit(-1);
	}

	exit(read_until_close(sock, timeout));
    } else {
        /*
         * We're a server.  Listen, and loop indefinitely
         * accepting connections.
         */
	struct sigaction sa;

	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = child_handler;
	if (sigaction(SIGCHLD, &sa, NULL)) {
	    fprintf(stderr, "sigaction for SIGCHLD failed\n");
	    exit(-1);
	}
	
	c = 1;
	if (setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (void *)&c, sizeof (c)) != 0) {
	    perror("setsockopt");
	    exit(-1);
	}
	
#ifdef HAVE_SIN_LEN
	name.sin_len = 16;
#endif
	name.sin_family = AF_INET;
	name.sin_addr.s_addr = 0;	/* allow connection on any
					 * interface */
	name.sin_port = htons(port);
	if (bind(sock, (struct sockaddr *) &name, sizeof(name)) == -1) {
	    perror("Bind failed");
	    exit(-1);
	}

	/*
	 * listen for new connections 
	 */
	do {
	    result = listen(sock, 5);
	} while ((result == -1) && (errno == EINTR));
	if (result == -1) {
	    perror("Listen failed");
	    exit(-1);
	}

	if (daemon) daemonize();
	/* Don't count on stdio from here on, use log() instead */
	log(LOG_INFO, "Listening on TCP port: %d\n", port);
	
	while (1) {
	    char *peerstr;
	    
	    newnamelen = sizeof(newname);
	    do {
		newsock = accept(sock, (struct sockaddr *) &newname,
				 &newnamelen);
	    } while ((newsock == -1) && (errno == EINTR));
	    if (newsock == -1) {
		log(LOG_ERR, "Accept failed: %s\n", strerror(errno));
		/* could be temporary, don't die */
		continue;
	    }
	    peerstr = inet_ntoa(newname.sin_addr);  // NOTE: Static buf

#ifdef LIBWRAP
	    {
		struct request_info req;

		request_init(&req, RQ_DAEMON, DAEMON, RQ_FILE, newsock, 0);
		fromhost(&req);

		if (!hosts_access(&req)) {
			log(LOG_INFO, "Connection refused from %s\n", peerstr);
			close(newsock);
			continue;
		}
	    }
#endif

	    if (!child_avail) {
		log(LOG_ERR, "Too many clients, refusing %s\n", peerstr);
		close(newsock);
		continue;
	    }

	    pid = fork();
	    if (!pid) {
		/*
		 * I am the child process 
		 */
		int ret;

		/* don't hold onto the listening socket */
		close(sock);

		log(LOG_INFO, "Connection from %s:%d\n", peerstr,
				ntohs(newname.sin_port));
		ret = read_until_close(newsock, timeout);
		log(LOG_INFO, "Connection %s\n",
				(alarmed) ? "timeout" : "closed");
		exit(ret);
	    } else if (pid < 0) {
		log(LOG_ERR, "Fork failed");
		/* could be temporary, don't die */
		close(newsock);
		continue;
	    }
	    /*
	     * Otherwise, I am the parent.
	     * Close the accepted socket, down our available count and loop
	     */
	    close(newsock);
	    child_down();
	}
    }

    return 0;
}

