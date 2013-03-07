/******************************************************************************
 * pathprobe.h, pathlib.c                                                     *
 *                                                                            *
 * A library of Web100 MIB tools to help use TCP to probe path properties     *
 * Matt Mathis, mathis@psc.edu                                                *
 * Raghu Reddy, rreddy@psc.edu                                                *
 * Pittsburgh Supercomputing Center                                           *
 * Feb 2004                                                                   *
 *                                                                            *
 *   Note: /usr/local/lib must be in LD_LIBRARY_PATH                          *
 *                                                                            *
 ******************************************************************************/

#include <stdlib.h>

//
// terse wins
//
#define QUITZ(v, m)   {if (!(v))              {perror(m); exit(1);}}
#define QUITNZ(v, m)  {if ( (v))              {perror(m); exit(1);}}
#define QUITNEG(v, m) {if (((int)(v)) < 0)    {perror(m); exit(1);}}
#define CHECK(v, m)   {if (!(v))              {fprintf(stderr, "%s\n", (m)); exit(1);}}
//
// web100 error checking shortcuts
//
#define WC_QUITZ(v, m)   {if (!(v))           { web100_perror(m); exit(2); }}
#define WC_QUITNZ(v, m)  {if ( (v))           { web100_perror(m); exit(2); }}
#define WC_QUITNEG(v, m) {if (((int)(v)) < 0) { web100_perror(m); exit(2); }}

#define DIV(n, d)  ((d) ? (n)/(d) : 999999)
#define FDIV(n, d) ((d) ? ((float)(n))/(d) : 999999.0)

//===================================================================
// Short cuts for getting values/deltas of variables
//
#ifndef MYDEF
#ifdef MKFUNCTIONS
#define MYDEF_GAUGE(name, type)\
type web100_get_##name(web100_snapshot *a) {\
 type t1;\
 static web100_var *va;\
 if (!va) WC_QUITZ(va=web100_var_find(web100_get_snap_group(a), #name),"var not found");\
 WC_QUITNZ(web100_snap_read(va, a, &t1), "snap_read"); \
 return (t1);\
}

#define MYDEF_COUNTER(name, type)\
MYDEF_GAUGE(name, type) \
type web100_delta_##name(web100_snapshot *a, web100_snapshot *b){\
 type t1;\
 static struct web100_var *va;\
 if (!va) WC_QUITZ(va=web100_var_find(web100_get_snap_group(a), #name),"var not found");\
 WC_QUITNZ(web100_delta_any(va, a, b, &t1), "delta failed");\
 return t1;\
}
#else
#define MYDEF_GAUGE(name, type) \
    type web100_get_##name(web100_snapshot *a);
#define MYDEF_COUNTER(name, type) \
    MYDEF_GAUGE(name, type) \
    type web100_delta_##name(web100_snapshot *a, web100_snapshot *b) ;
#endif

MYDEF_COUNTER(Duration, unsigned long long);
MYDEF_COUNTER(SndNxt, unsigned int);
MYDEF_COUNTER(SndMax, unsigned int);
MYDEF_COUNTER(SndUna, unsigned int);
MYDEF_COUNTER(CongestionSignals, unsigned int);
MYDEF_COUNTER(PostCongCountRTT, unsigned int);
MYDEF_GAUGE(CurCwnd, unsigned int);
MYDEF_GAUGE(CurMSS, unsigned int);
MYDEF_GAUGE(TimestampsEnabled, int);
MYDEF_GAUGE(SACKEnabled, int);
MYDEF_GAUGE(WinScaleRcvd, int);
MYDEF_COUNTER(CountRTT, unsigned int);
MYDEF_COUNTER(SumRTT, unsigned long long);
#endif

#define SEQ_GT(a, b) (((b)-(a))&0x80000000)

//******************************************************************************
// global variables
//
web100_agent      	      *ag;           // agent
web100_connection 	      *conn;         // connection
web100_log                    *vlog;

web100_group                  *gread;        // read group
web100_group                  *gtune;        // tune group

struct web100_readbuf {
    char padding[128];
} obuf, nbuf;				     // Buffer for converting data



#ifdef MKFUNCTIONS
const int OneSec = 1000000;
#else 
const int OneSec;
#endif

//
// Test control structure
//
struct tctrl {
  int flag;		/* indicates usage         	  */
  int basemss;		/* Base MSS in Bytes       	  */
  int win;		/* Peak Window in packets  	  */
  int burstwin;		/* burst size in packets   	  */
  int duration;		/* test duration in us     	  */     
  int obswin;		/* maximum observed window, Bytes */
		/* statistics on the transmit tuning process */
  int SSbursts;		/* Number of successfully sent bursts */
  int SSbully;		/* we had to push */
  int SSbullyStall;	/* TCP pushed back - not in CA or something */
  int SSsumAwnd;	/* sum awnd */
  int SScntAwnd;	/* count of awnd samples */
  int SSpoll;		/* count of TCP polls from pathlib */
};

struct stats {
  struct tctrl    tc;
  web100_snapshot *snap;
};

//******************************************************************************
// Function declarations
//

/* private */
typedef int elapsed_pred(web100_snapshot *, web100_snapshot *,void *);
web100_snapshot *watch_sample(web100_connection *conn, elapsed_pred done, void *arg);
int  	    elapsed_usec(web100_snapshot *start, web100_snapshot *current, void *arg);
int         stune_conn(web100_connection *conn, int swindow);

/* used from python */
web100_snapshot *watch_elapsed_sample(web100_connection *conn, struct tctrl *arg);
int write_web100_var(web100_connection *conn, web100_group *gr, char *name, int val);
