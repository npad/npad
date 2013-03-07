/* trafficrcv.c
 * 
 * Data sink for TCP transfer tests
 *
 * Jeffrey Semke, Matthew Mathis, and Raghu Reddy
 * Pittsburgh Supercomputing Center
 * August 1999; Revised on Mar 2002
 */

/* $Id: trafficrcv-win.c,v 1.1.1.1 2005/06/06 16:06:32 jheffner Exp $ */

/*
 * Thanks to Shirl Grant and John Heffner for their testing on FreeBSD and
 * Linux.  I have incorporated their patches to make this work on more than
 * just NetBSD.
 */

#include <sys/types.h>		/* for FreeBSD                          */
#include <stdio.h>		/* for stderr                           */
#include <stdlib.h>		/* for random 				*/
#include <errno.h>		/* for errno                            */
#include <winsock.h>
#include <sys/types.h>
#include <string.h>
#include <sys/timeb.h>


#ifndef TPORT
#define TPORT	56117           /* default port; use -p port to change  */
#endif
#ifndef APPBUF
#define APPBUF	(1024 * 1024)
#endif
#ifndef REPS
#define REPS	100
#endif

static void
usage(char name[])
{
	fprintf(stderr, "Usage: %s [-p port] [-b sockbuf_bufsize] [sockbuf_size]\n", name);
}

static void
finish(int sock, struct sockaddr_in name)
{
      int	result;
      char	message[256];

      do {
	    result = shutdown(sock, 2);
      } while ((result == -1) && (errno == EINTR));
      if (result == -1) {
	    perror("Error closing connection");
	    exit(-1);
      }

      sprintf(message, "Connection from %s:%d",
		inet_ntoa(name.sin_addr),
		ntohs(name.sin_port));
}

int
main(int argc, char *argv[])
{
      int	opt_len;
      struct sockaddr_in name, newname;
      int	newnamelen;
      long	bufsize = 0;			/* use default */
      long	bufsizea = 0;			/* actual bufsize */
      int	result, rbytes, bytes;
      char	*databuf;
      int	sock, newsock;
      int	status;			/* dummy var needed for waitpid */
      int       port = TPORT;
      int       errflg = 0;
      int       c;
      int   i ;
	  WSADATA wsdata ;

// checking for -p and -b args, not sockbuf_size

    for( i = 1 ; i < argc ; i++ ) {
	    
	    if( (strcmp("-p",argv[i]) == 0) && ((i + 1) < argc) ) {
		 	port = atoi(argv[i+1]) ;   
		 	i++ ;
	   	}
	    
	    if( (strcmp("-b",argv[i]) == 0) && ((i + 1) < argc) ) {
		 	bufsize = atoi(argv[i+1]) ;   
		 	i++ ;
	   	}
	    
	}
    
    if (errflg) {
      usage(argv[0]);
      exit (2);
    }

    
	
	  // tell windows sockets to start up
	  WSAStartup(MAKEWORD(2,0), &wsdata) ;    
    
      /* Create a socket to test with*/

      if ((sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
	    perror("Couldn't create a socket");
	    exit(-1);
      }

      /* Set the buffer size, if specified */
      opt_len = sizeof(bufsize);

      if (bufsize) {
#if 0                                  /* not sure why this was set?  rreddy */
	    if (setsockopt(sock, SOL_SOCKET, SO_SNDBUF, (void *)&bufsize, opt_len)) {
		  perror("Couldn't set send socket buffer size");
		  exit(-1);
	    }
#endif
	    if (setsockopt(sock, SOL_SOCKET, SO_RCVBUF, (void *)&bufsize, opt_len)) {
		  perror("Couldn't set receive socket buffer size");
		  exit(-1);
	    }
      }
      if (getsockopt(sock, SOL_SOCKET, SO_RCVBUF, (void *)&bufsizea, &opt_len)) {
	  perror("Couldn't get receive socket buffer size");
	  exit(-1);
      }
      //
      // actually buffer size is 1/2 (hence the shift) the value returned
      // by getsockopt because this includes retransmit buffer
      //
      fprintf(stdout, "Getsockopt() reports %d byte socket buffers\n", bufsizea);

      /* Set up a well-known port */
#ifdef HAVE_SIN_LEN
      name.sin_len		= 16;
#endif
      name.sin_family		= AF_INET;
      name.sin_addr.s_addr	= 0;	/* allow connection on any interface */
      name.sin_port		= htons(port);

      if (bind(sock, (struct sockaddr*)&name, sizeof(name)) == -1) {
	    perror("Bind failed");
	    exit(-1);
      }

      /* Set up data buffer */
      if ((databuf = malloc(APPBUF))  == NULL) {
	    fprintf(stderr, "Malloc of data buffer failed\n");
	    exit(-1);
      }

      fprintf(stderr, "Listening on TCP port: %d\n",port);
      /* listen for new connections */
      do {
	    result = listen(sock, 5);
      } while ((result == -1) && (errno == EINTR));
      if (result == -1) {
	    perror("Listen failed");
	    exit(-1);
      }

      /* Start loop to accept connections and receive data. */

      while (1) {

	    /* accept new connections when they come in */
	    newnamelen = sizeof(newname);
	    do {
		  newsock = accept(sock, (struct sockaddr*)&newname,
				   &newnamelen);
	    } while ((newsock == -1) && (errno == EINTR));
	    if (newsock == -1) {
		  perror ("Accept failed");
		  exit(-1);
	    }

#if 0	/* TEST CODE */
	    addr = newname.sin_addr.s_addr;
	    for (i = 0; i < 4; i++) {
		  printf("%d.", addr & 0xFF);
		  addr = addr >> 8;
	    }
	    printf("%d\n", ntohs(newname.sin_port));
#endif	/* END TEST CODE */


		  /* Receive data */
		  bytes = APPBUF;
		  do {
			rbytes = read(newsock, databuf, bytes);
			if (rbytes == -1) {
			      if (errno != EINTR) {
				    perror("Recv");
				    /* close socket and exit */
				    finish(newsock, newname);
				    exit(-1);   
			      } else
				    rbytes = 1;  /* clear the error and 
						    read again */
			}
		  } while (rbytes > 0);

		  /* Close the connection */
		  finish(newsock, newname);
		  WSACleanup() ;
		  exit(0);

      }
}

