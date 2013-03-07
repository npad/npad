%module pathlib
%{
/* Includes the header in the wrapper code */
/* our modified version */
#include "web100/web100.h"
#define MYDEF
#include "pathlib.h"

int baseMSS;
%}

//****************************************************************
// Import everything in pathlib.h
//

%include "pathlib.h"

//****************************************************************
//  Misc stuff (mostly stubs) from pyprobe.c
//
%extend tctrl {
	struct tctrl *copy() {
		struct tctrl *r = malloc (sizeof(struct tctrl));
		*r = *self;
		return(r);
	}
}

int baseMSS;

pid_t pumpsegs(int datasock, int bufsize);


