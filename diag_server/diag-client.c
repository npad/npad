#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>

#define VERSION			0
#define LINE_LEN		1024
#define WHITESPACE		"\t\n\v\f\r "
#define DISCARD_BUFSIZE		(16*1024)

int discard_child(struct sockaddr_in *addr)
{
	pid_t pid;
	int sock;
	char buf[DISCARD_BUFSIZE];
	
	if ((sock = socket(addr->sin_family, SOCK_STREAM, 0)) < 0) {
		perror("sock");
		exit(1);
	}
	if (connect(sock, (struct sockaddr *)addr, sizeof (struct sockaddr_in)) != 0) {
		perror("connect");
		exit(1);
	}
	
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

int main(int argc, char *argv[])
{
	char *serv_name;
	int port, rtt, rate;
	struct sockaddr_in serv_addr;
	struct hostent *serv_hent;
	int control_sock;
	FILE *control_in, *control_out;
	int handshake;
	
	/* Parse args */
	if (argc <  3) {
		fprintf(stderr, "Usage: %s server port [rtt] [rate]\n", argv[0]);
		exit(1);
	}
	serv_name = argv[1];
	port = atoi(argv[2]);

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
	if ((serv_hent = gethostbyname(serv_name)) == NULL) {
		fprintf(stderr, "gethostbyname: failed: %s\n", serv_name);
		exit(1);
	}
	serv_addr.sin_family = AF_INET;
	memcpy(&serv_addr.sin_addr.s_addr, serv_hent->h_addr_list[0], sizeof (in_addr_t));
	serv_addr.sin_port = htons(port);
	if ((control_sock = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
		perror("socket");
		exit(1);
	}
	if (connect(control_sock, (struct sockaddr *)&serv_addr, sizeof (serv_addr)) != 0) {
		perror("connect");
		exit(1);
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
	
	/* Main loop reading commands from server, line-based */
	handshake = 0;
	while (!feof(control_in)) {
		int c, i;
		char line[LINE_LEN], parse_line[LINE_LEN];
		char *cmd[LINE_LEN];
		int cmdlen;
		int test_started = 0;
		
		/* Read one line (max 1024 chars).
		 * Remove newline, null terminate. */
		i = 0;
		while ((c = fgetc(control_in)) != '\n' && c != EOF) {
			if (c != '\r' && i < LINE_LEN - 1)
				line[i++] = (char)c;
		}
		line[i] = '\0';
		
		/* Tokenize */
		strcpy(parse_line, line);
		cmd[0] = strtok(parse_line, WHITESPACE);
		if (cmd[0] == NULL)
			continue;
		for (i = 1; (cmd[i] = strtok(NULL, WHITESPACE)) != NULL; i++)
			;
		cmdlen = i;
		
		/* Look for errors firs (this can happen on handshake
		 * version mismatch. */
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
			
			/* Handshake okay, start pathdiag */
			fprintf(control_out, "test_pathdiag %d %d\n", rtt, rate);
			continue;
		}
		
		if (!test_started) {
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
				/* Ignore the address the server send. */
				serv_addr.sin_port = htons(atoi(cmd[2]));
				printf("port = %s\n", cmd[2]);
				if (discard_child(&serv_addr) != 0)
					exit(1);
				test_started = 1;
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
