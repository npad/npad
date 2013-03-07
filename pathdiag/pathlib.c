/******************************************************************************
 * pathlib.h, pathlib.c                                                       *
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
#include <stdio.h>
#include "web100/web100.h" /* Use this line if using installed web100 library */
#define MKFUNCTIONS
#include "pathlib.h"

#include "pumpsegs.c"

//****************************************************************
// Globals used for parameter passing
//

int  baseMSS;		// bytes
int  bully;

/****************************************************************
 * Collect data for some specified time period
 */

web100_snapshot *watch_sample(web100_connection *conn, elapsed_pred done, void *arg)
{
  static web100_snapshot *ns;	        // a fresh sample
  static web100_snapshot *os;	        // the start of the current second
  static web100_snapshot *base;	        // the start of this watch

  web100_snapshot *ret;	                // pointer that is returned

  static unsigned long timecheck, timet;
  //
  // Allocate memory for snapshots; gread is a global variable for the read group
  //
  if (!os)           // static, so do it just once
    WC_QUITZ(os  =web100_snapshot_alloc(gread, conn), "Snapshot alloc for os");

  if (!ns)           // static, so do it just once
    WC_QUITZ(ns  =web100_snapshot_alloc(gread, conn), "Snapshot alloc for ns");

  if (!base) {        // static, so do it just once
    WC_QUITZ(base=web100_snapshot_alloc(gread, conn), "Snapshot alloc for base");
    WC_QUITNEG(web100_snap(base),"snap of base");
    timecheck = web100_get_Duration(base);  // XXX get of a counter
  }
  WC_QUITNEG(web100_snap_data_copy(os, base),"snap_data_copy");

  while (1) {
    WC_QUITNEG(web100_snap(ns),"snap of ns failed");

    if ((timet=web100_get_Duration(ns)) < timecheck) { // XXX get of a counter
      printf("NEG time %lu %lu\n", timet, timecheck);
    }

    timecheck=timet;

    if (done(base, ns, arg)) {        
      //
      // Allocate and copy for later processing ("looks" like a memory leak)
      //
      WC_QUITZ(ret  =web100_snapshot_alloc(gread, conn), "Snapshot alloc for res");
      WC_QUITNEG(web100_snap_data_copy(ret , ns),"snap_data_copy failed");
      //
      // the new snap becomes new base
      //
      WC_QUITNEG(web100_snap_data_copy(base, ns),"snap_data_copy failed");
      return (ret);
    }

    if (web100_get_Duration(ns) > OneSec) {
#if 0
      FPrintStats(stderr, (struct tctrl *)arg, '\r', ns, os);	/* XXX */
      fflush(stdout);
#endif
      WC_QUITNEG(web100_snap_data_copy(os, ns),"snap_data_copy failed");
    }
  }
}

int elapsed_usec(
		 web100_snapshot *start,
		 web100_snapshot *current,
		 void *arg){
  struct tctrl *p = arg;
  int            rv;
  struct timeval tv;

  /* do we have enough data? */

  if (web100_delta_Duration(current, start) >= p->duration) {
    return 1;
  }
  else { /* no, so send more date */
    static web100_var *vWADCwndAdjust;
    static int wdrain, targetw, push;
    unsigned int awnd = web100_get_SndNxt(current) - web100_get_SndUna(current);
    unsigned int inrecov = web100_get_CongestionSignals(current) - web100_get_PostCongCountRTT(current);
    long temp, behind;

    if (!vWADCwndAdjust) WC_QUITZ( (vWADCwndAdjust=web100_var_find(gtune, "WAD_CwndAdjust") ),"WAD_CwndAdjust - Not found" );

    // get some stats on awnd
    if (inrecov == 0) {
	p->SSsumAwnd += awnd;
	p->SScntAwnd++;
	if (awnd > p->obswin) p->obswin = awnd;
    }

    // possibly do unadulterated congestion control (slow start?)
    if (p->win == 0) {
	return 0;
    }

    // burst by  toggling in and out of drain state
    if (!wdrain) {
      if (targetw != p->win) {			// Set the window
	targetw = p->win;
	push++;
	stune_conn(conn, baseMSS*targetw);
      }
      if (p->burstwin && awnd >= baseMSS*targetw) // transition into drain state
	wdrain = 1;
    } else {
     if (targetw != p->win - p->burstwin) {	// set the drained window
	targetw = p->win - p->burstwin;
	stune_conn(conn, baseMSS*targetw);
	p->SSbursts++;
      }
      if (awnd <= baseMSS*targetw)		// transtion outof drain state
	wdrain = 0;
    }

    // Be a bully and stiffen TCP (unbuffered calls)
    behind = targetw - web100_get_CurCwnd(current)/baseMSS;
    if ((push||bully) && behind>0){
      WC_QUITNEG(web100_raw_read(vWADCwndAdjust, conn, &temp), "WAD_CwndAdjust - failed read");
      if (temp==0) {
	push = 0;
        p->SSbully++;
        WC_QUITNEG(web100_raw_write(vWADCwndAdjust, conn, &behind), "WAD_CwndAdjust - failed");
      } else
	p->SSbullyStall++;
    }

    p->SSpoll++;

#if 1
    tv.tv_sec  = 0;
    tv.tv_usec = 1000;
    rv = select((int)NULL, NULL, NULL, NULL, &tv);
#endif
    return 0;
  }
}
/****************************************************************
 * Tune a connection
 * 	Beware that this uses unbuffered calls
 */
int stune_conn(web100_connection *conn, int swindow) {

  static web100_var *vLimCwndTune=0, *vLimCwndRead=0, *vSndbufTune=0;

  int check, bufsz = 3*swindow;
  static maxbuf=0;

  if (!vLimCwndTune) WC_QUITZ( (vLimCwndTune=web100_var_find(gtune, "LimCwnd") ),"LimCwnd tune - Not found" );
  if (!vSndbufTune) WC_QUITZ( (vSndbufTune=web100_var_find(gtune, "X_Sndbuf") ),"X_Sndbuf tune - Not found" );
  if (!vLimCwndRead) WC_QUITZ( (vLimCwndRead=web100_var_find(gread, "LimCwnd") ),"LimCwnd - Not found" );

  WC_QUITNEG(web100_raw_write(vLimCwndTune, conn, &swindow       ),"Web100 failed to write LimCwnd");
  // only set the socket buffer up
  if (bufsz>maxbuf) {
      maxbuf=bufsz;
      // Enable this to defeat sender side autotuning
      //      WC_QUITNEG(web100_raw_write(vSndbufTune, conn, &bufsz       ),"Sndbuf Set");
  }

  WC_QUITNEG(web100_raw_read (vLimCwndRead, conn, &check         ),"LimCwnd Verify");

  // Note that this code implicitly verifies that CurMSS is correct
  // Beware that this might be the only ongoing check on CurMSS
  // XXXX should raise a proper error, not exit

  if (swindow != check) {
    fprintf (stderr, "failed to set window: Tried %d, Got back %d\n", swindow, check);
    exit(1);
  }
  return(swindow);
}

/* Interim code to avoid passing c pointers through python */
web100_snapshot *watch_elapsed_sample(web100_connection *conn, struct tctrl *arg) {
    return(watch_sample(conn, elapsed_usec, arg));
}

int write_web100_var(web100_connection *conn, web100_group *gr, char *name, int val) {
    web100_var *v = web100_var_find(gr, name);
    return(web100_raw_write(v, conn, &val));
}
