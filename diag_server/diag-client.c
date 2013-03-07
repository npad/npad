#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

/* This version updated to support both IPv4 and IPv6 */
#define VERSION			0
#define LINE_LEN		1024
#define WHITESPACE		"\t\n\v\f\r "
#define DISCARD_BUFSIZE		(16*1024)

const int debug=0;	/* make the compiler fix it*/

void showbytes(unsigned char *str, int len)
{
  while (len--) printf ("%02x", *str++);
}

int discard_child(struct addrinfo *addr)
{
	pid_t pid;
	int sock;
	char buf[DISCARD_BUFSIZE];
	
	if ((sock = socket(addr->ai_family, addr->ai_socktype, addr->ai_protocol)) < 0) {
		perror("sock");
		exit(1);
	}
	if (connect(sock, addr->ai_addr, addr->ai_addrlen) != 0) {
		perror("discard connect");
		exit(1);
	}
	if (debug) printf("Discarding\n");
	if ((pid = fork()) < 0) {
		perror("fork");
		return -1;
	} else if (pid == 0) {
		/* Child */
		while (read(sock, buf, DISCARD_BUFSIZE) > 0)
			;
		exit(0);
	}
	close(sock);
	
	return 0;
}
#define MAXEXTRAS 1024

int main(int argc, char *argv[])
{
  char *serv_name, *port;
	int rtt, rate, r;
	struct addrinfo *result, *serv_addr;
	int control_sock;
	FILE *control_in, *control_out;
	int handshake = 0, test_started = 0, extra_args=0;
	char *extras=0, extrabuf[MAXEXTRAS], *ap, *cp=extrabuf;
	struct addrinfo hint = {
	  .ai_family = AF_UNSPEC,
	  .ai_socktype = SOCK_STREAM,
	  .ai_flags = AI_ADDRCONFIG|AI_NUMERICSERV|AI_CANONNAME,
	};

	/* all args that start with '-' are passed to the server via the extra_args command */
	cp=extrabuf;
	while (argc > 1 && cp < &extrabuf[MAXEXTRAS]) {
		if (argv[1][0] != '-')
			break;
		*cp++ = ' ';
		for (ap=argv[1];*ap && cp < &extrabuf[MAXEXTRAS-1];)
			*cp++ = *ap++;
		*cp = '\0';
		extras=extrabuf;
		argv++;
		argc--;
	}

	/* Parse remaining args */
	if (argc <  3) {
		fprintf(stderr, "Usage: %s server port [rtt] [rate]\n", argv[0]);
		exit(1);
	}
	serv_name = argv[1];
	port = argv[2];

	if (argc < 4) {
		rtt = 10;
	} else {
		rtt = atoi(argv[3]);
	}
	if (argc < 5) {
		rate = 20;
	} else {
		rate = atoi(argv[4]);
	}
	printf("Using: rtt %d ms and rate %d\n" , rtt, rate);
	
	/* Lookup server name and establish control connection */
	r = getaddrinfo(serv_name, port, &hint, &result);
	if (r != 0) {
	  fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(r));
	  exit(-1);
	}

        for (serv_addr = result; serv_addr != NULL; serv_addr = serv_addr->ai_next) {
	  char buf[INET_ADDRSTRLEN];

	  showbytes((unsigned char *)serv_addr->ai_addr, sizeof(serv_addr->ai_addr));
	  printf(" Trying (%s) (%s)\n", serv_addr->ai_canonname,
		 inet_ntop(serv_addr->ai_family, serv_addr->ai_addr, buf, INET_ADDRSTRLEN ));

	  control_sock = socket(serv_addr->ai_family, serv_addr->ai_socktype, serv_addr->ai_protocol);
	  if (control_sock == -1)
	    continue;

	  if (connect(control_sock, serv_addr->ai_addr, serv_addr->ai_addrlen) != -1) {
	    printf("Connect %d\n", control_sock);
	    break;                  /* Success */
	  }

	  close(control_sock);
	}
	if (!serv_addr) {
	  fprintf(stderr, "Could not connect\n");
	  exit -1;
	}

	if ((control_in = fdopen(control_sock, "r")) == NULL ||
	    (control_out = fdopen(control_sock, "w")) == NULL) {
		perror("fdopen");
		exit(1);
	}
	setlinebuf(control_in);
	setlinebuf(control_out);
	printf("Connected.\n");
	
	/* Tell the server we're here. */
	fprintf(control_out, "handshake %d\n", VERSION);
	if (debug) printf("Sent: handshake %d\n", VERSION);
	
	/* Main loop reading commands from server, line-based */
	while (!feof(control_in)) {
		int c, i;
		char line[LINE_LEN], parse_line[LINE_LEN];
		char *cmd[LINE_LEN];
		int cmdlen;
		
		/* Read one line (max 1024 chars).
		 * Remove newline, null terminate. */
		i = 0;
		while ((c = fgetc(control_in)) != '\n' && c != EOF) {
			if (c != '\r' && i < LINE_LEN - 1)
				line[i++] = (char)c;
		}
		line[i] = '\0';
		if (debug) printf("Input: %s\n", line);
		
		/* Tokenize */
		strcpy(parse_line, line);
		cmd[0] = strtok(parse_line, WHITESPACE);
		if (cmd[0] == NULL)
			continue;
		for (i = 1; (cmd[i] = strtok(NULL, WHITESPACE)) != NULL; i++)
			;
		cmdlen = i;
		
		/* Look for errors first (this can happen on handshake
		 * version mismatch). */
		if (!strcmp(cmd[0], "error")) {
			printf("%s\n", line);
			exit(1);
		}
		
		/* Make sure we complete the handshake first. */
		if (!handshake) {
			if (strcmp(cmd[0], "handshake") || cmdlen < 2) {
				printf("Protocol error: bad handshake.\n"
				       "Please make sure you have the latest client, "
				       " and you have the correct port number.\n");
				exit(1);
			}
			printf("Control connection established.\n");
			handshake = 1;
			/* Handshake okay, drop through */
		}
		if (extras) {
			if (extra_args == 0) {
				fprintf(control_out, "extra_args %s\n", extras);
				if (debug) printf("sent: extra_args %s\n", extras);
				extra_args = 1;
				continue;
			} else if (extra_args == 1) {
				if (strcmp(cmd[0], "extra_args") || cmdlen < 2 || strcmp(cmd[1], "OK")) {
					fprintf(stderr, "Protocol error: extra args were rejected\n%s\n", line);
					exit(1);
				}
				extra_args = 2;
			}
		}
		if (test_started == 0) {
			fprintf(control_out, "test_pathdiag %d %d\n", rtt, rate);
			if (debug) printf("sent: test_pathdiag %d %d\n", rtt, rate);
			test_started = 1;
			continue;
		} else if (test_started == 1) {
			if (!strcmp(cmd[0], "queue_depth")) {
				if (cmdlen < 2) {
					fprintf(stderr, "Protocol warning: bad queue_depth command.\n");
					continue;
				}
				printf("Waiting for test to start.  "
					   "Currently there are %d tests ahead of yours.\n",
					   atoi(cmd[1]));
				continue;
			} else if (!strcmp(cmd[0], "listen")) {
				if (cmdlen < 3) {
					fprintf(stderr, "Protocol error: bad listen command.\n");
					exit(1);
				}
				/* Override the port for data connection. */
				printf("port = %s\n", cmd[2]);
				{
				  struct sockaddr_in *sin = (struct sockaddr_in *) serv_addr->ai_addr;
				  sin->sin_port = htons(atoi(cmd[2]));
				}
				if (discard_child(serv_addr) != 0)
					exit(1);
				test_started = 2;
				printf("Starting test.\n");
				continue;
			}
		}
		if (!strcmp(cmd[0], "info")) {
			printf("%s\n", line + 5);
		} else if (!strcmp(cmd[0], "report")) {
			printf("%s\n", line);
			break;
		} else {
			fprintf(stderr, "Warning: unexpected command %s\n", cmd[0]);
		}
	}
	
	return 0;
}
