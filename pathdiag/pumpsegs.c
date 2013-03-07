/* pumpsegs.c
 * 
 * Matt Mathis, mathis@psc.edu
 * Raghu Reddy, rreddy@psc.edu
 * Pittsburgh Supercomputing Center
 * Jan 2004
 *
 * Purpose:
 *     This program is used by pathdiag.c. 
 *     The purpose of this program is to spawn a task
 *     and keep pumping data into a give socket file
 *     descriptor.
 *     Check every second to see if the parent has exited.
 */
#include<stdio.h>
#include <errno.h>
#include<sys/types.h>
#include <sys/time.h>
#include<unistd.h>
#include <signal.h>

/* on every signal check to see if we are detached */
void thand (int zip) {
    if ( getppid() == 1 ) {
	exit (1);
    }
};

struct itimerval intival;
struct sigaction siga;

pid_t pumpsegs(int datasock, int bufsize)
{
    char *buf;
    pid_t pid;
    int   ret;    // Return code
    int   i;
    sigset_t set;
    
    //
    // Ignore so that parent is not required to do a wait
    //
    signal(SIGCHLD, SIG_IGN);
    if( (pid = fork()) < 0 ){
        perror("fork");
	exit(1);
    }    
    else if ( pid == 0 ){  // Child

	// set up the signal (1Hz) and handler
	siga.sa_handler = thand;
	siga.sa_flags = SA_RESTART;
	sigaction(SIGALRM, &siga, 0);
	intival.it_interval.tv_sec = 1;
	intival.it_value.tv_sec = 1;
	setitimer(ITIMER_REAL, &intival, 0);
	
	sigemptyset(&set);
	sigaddset(&set, SIGALRM);
	if (sigprocmask(SIG_UNBLOCK, &set, NULL) != 0)
		perror("sigprocmask");

        buf = (char *)malloc(bufsize);
	while(1){
	    ret=write(datasock, buf, bufsize);
	    if( ret < 0 ){
		if (errno == EINTR) {
		    errno = 0;
		    continue;
		}
		fprintf(stderr, "pumpsegs: write failed (%d, %d)\n", ret, errno);
		exit(1);
	    }
	}
    }
    // Child never comes to this part
    return pid;
}
