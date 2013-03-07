# This file was created automatically by SWIG.
# Don't modify this file, modify the SWIG interface instead.
# This file is compatible with both classic and new-style classes.

import _pathlib

def _swig_setattr_nondynamic(self,class_type,name,value,static=1):
    if (name == "this"):
        if isinstance(value, class_type):
            self.__dict__[name] = value.this
            if hasattr(value,"thisown"): self.__dict__["thisown"] = value.thisown
            del value.thisown
            return
    method = class_type.__swig_setmethods__.get(name,None)
    if method: return method(self,value)
    if (not static) or hasattr(self,name) or (name == "thisown"):
        self.__dict__[name] = value
    else:
        raise AttributeError("You cannot add attributes to %s" % self)

def _swig_setattr(self,class_type,name,value):
    return _swig_setattr_nondynamic(self,class_type,name,value,0)

def _swig_getattr(self,class_type,name):
    method = class_type.__swig_getmethods__.get(name,None)
    if method: return method(self)
    raise AttributeError,name

import types
try:
    _object = types.ObjectType
    _newclass = 1
except AttributeError:
    class _object : pass
    _newclass = 0
del types



web100_get_Duration = _pathlib.web100_get_Duration

web100_delta_Duration = _pathlib.web100_delta_Duration

web100_get_SndNxt = _pathlib.web100_get_SndNxt

web100_delta_SndNxt = _pathlib.web100_delta_SndNxt

web100_get_SndMax = _pathlib.web100_get_SndMax

web100_delta_SndMax = _pathlib.web100_delta_SndMax

web100_get_SndUna = _pathlib.web100_get_SndUna

web100_delta_SndUna = _pathlib.web100_delta_SndUna

web100_get_CongestionSignals = _pathlib.web100_get_CongestionSignals

web100_delta_CongestionSignals = _pathlib.web100_delta_CongestionSignals

web100_get_PostCongCountRTT = _pathlib.web100_get_PostCongCountRTT

web100_delta_PostCongCountRTT = _pathlib.web100_delta_PostCongCountRTT

web100_get_CurCwnd = _pathlib.web100_get_CurCwnd

web100_get_CurMSS = _pathlib.web100_get_CurMSS

web100_get_TimestampsEnabled = _pathlib.web100_get_TimestampsEnabled

web100_get_SACKEnabled = _pathlib.web100_get_SACKEnabled

web100_get_WinScaleRcvd = _pathlib.web100_get_WinScaleRcvd

web100_get_CountRTT = _pathlib.web100_get_CountRTT

web100_delta_CountRTT = _pathlib.web100_delta_CountRTT

web100_get_SumRTT = _pathlib.web100_get_SumRTT

web100_delta_SumRTT = _pathlib.web100_delta_SumRTT
class web100_readbuf(_object):
    __swig_setmethods__ = {}
    __setattr__ = lambda self, name, value: _swig_setattr(self, web100_readbuf, name, value)
    __swig_getmethods__ = {}
    __getattr__ = lambda self, name: _swig_getattr(self, web100_readbuf, name)
    def __repr__(self):
        return "<%s.%s; proxy of C web100_readbuf instance at %s>" % (self.__class__.__module__, self.__class__.__name__, self.this,)
    __swig_setmethods__["padding"] = _pathlib.web100_readbuf_padding_set
    __swig_getmethods__["padding"] = _pathlib.web100_readbuf_padding_get
    if _newclass:padding = property(_pathlib.web100_readbuf_padding_get, _pathlib.web100_readbuf_padding_set)
    def __init__(self, *args):
        _swig_setattr(self, web100_readbuf, 'this', _pathlib.new_web100_readbuf(*args))
        _swig_setattr(self, web100_readbuf, 'thisown', 1)
    def __del__(self, destroy=_pathlib.delete_web100_readbuf):
        try:
            if self.thisown: destroy(self)
        except: pass


class web100_readbufPtr(web100_readbuf):
    def __init__(self, this):
        _swig_setattr(self, web100_readbuf, 'this', this)
        if not hasattr(self,"thisown"): _swig_setattr(self, web100_readbuf, 'thisown', 0)
        _swig_setattr(self, web100_readbuf,self.__class__,web100_readbuf)
_pathlib.web100_readbuf_swigregister(web100_readbufPtr)
cvar = _pathlib.cvar

class tctrl(_object):
    __swig_setmethods__ = {}
    __setattr__ = lambda self, name, value: _swig_setattr(self, tctrl, name, value)
    __swig_getmethods__ = {}
    __getattr__ = lambda self, name: _swig_getattr(self, tctrl, name)
    def __repr__(self):
        return "<%s.%s; proxy of C tctrl instance at %s>" % (self.__class__.__module__, self.__class__.__name__, self.this,)
    __swig_setmethods__["flag"] = _pathlib.tctrl_flag_set
    __swig_getmethods__["flag"] = _pathlib.tctrl_flag_get
    if _newclass:flag = property(_pathlib.tctrl_flag_get, _pathlib.tctrl_flag_set)
    __swig_setmethods__["basemss"] = _pathlib.tctrl_basemss_set
    __swig_getmethods__["basemss"] = _pathlib.tctrl_basemss_get
    if _newclass:basemss = property(_pathlib.tctrl_basemss_get, _pathlib.tctrl_basemss_set)
    __swig_setmethods__["win"] = _pathlib.tctrl_win_set
    __swig_getmethods__["win"] = _pathlib.tctrl_win_get
    if _newclass:win = property(_pathlib.tctrl_win_get, _pathlib.tctrl_win_set)
    __swig_setmethods__["burstwin"] = _pathlib.tctrl_burstwin_set
    __swig_getmethods__["burstwin"] = _pathlib.tctrl_burstwin_get
    if _newclass:burstwin = property(_pathlib.tctrl_burstwin_get, _pathlib.tctrl_burstwin_set)
    __swig_setmethods__["duration"] = _pathlib.tctrl_duration_set
    __swig_getmethods__["duration"] = _pathlib.tctrl_duration_get
    if _newclass:duration = property(_pathlib.tctrl_duration_get, _pathlib.tctrl_duration_set)
    __swig_setmethods__["obswin"] = _pathlib.tctrl_obswin_set
    __swig_getmethods__["obswin"] = _pathlib.tctrl_obswin_get
    if _newclass:obswin = property(_pathlib.tctrl_obswin_get, _pathlib.tctrl_obswin_set)
    __swig_setmethods__["SSbursts"] = _pathlib.tctrl_SSbursts_set
    __swig_getmethods__["SSbursts"] = _pathlib.tctrl_SSbursts_get
    if _newclass:SSbursts = property(_pathlib.tctrl_SSbursts_get, _pathlib.tctrl_SSbursts_set)
    __swig_setmethods__["SSbully"] = _pathlib.tctrl_SSbully_set
    __swig_getmethods__["SSbully"] = _pathlib.tctrl_SSbully_get
    if _newclass:SSbully = property(_pathlib.tctrl_SSbully_get, _pathlib.tctrl_SSbully_set)
    __swig_setmethods__["SSbullyStall"] = _pathlib.tctrl_SSbullyStall_set
    __swig_getmethods__["SSbullyStall"] = _pathlib.tctrl_SSbullyStall_get
    if _newclass:SSbullyStall = property(_pathlib.tctrl_SSbullyStall_get, _pathlib.tctrl_SSbullyStall_set)
    __swig_setmethods__["SSsumAwnd"] = _pathlib.tctrl_SSsumAwnd_set
    __swig_getmethods__["SSsumAwnd"] = _pathlib.tctrl_SSsumAwnd_get
    if _newclass:SSsumAwnd = property(_pathlib.tctrl_SSsumAwnd_get, _pathlib.tctrl_SSsumAwnd_set)
    __swig_setmethods__["SScntAwnd"] = _pathlib.tctrl_SScntAwnd_set
    __swig_getmethods__["SScntAwnd"] = _pathlib.tctrl_SScntAwnd_get
    if _newclass:SScntAwnd = property(_pathlib.tctrl_SScntAwnd_get, _pathlib.tctrl_SScntAwnd_set)
    __swig_setmethods__["SSpoll"] = _pathlib.tctrl_SSpoll_set
    __swig_getmethods__["SSpoll"] = _pathlib.tctrl_SSpoll_get
    if _newclass:SSpoll = property(_pathlib.tctrl_SSpoll_get, _pathlib.tctrl_SSpoll_set)
    def copy(*args): return _pathlib.tctrl_copy(*args)
    def __init__(self, *args):
        _swig_setattr(self, tctrl, 'this', _pathlib.new_tctrl(*args))
        _swig_setattr(self, tctrl, 'thisown', 1)
    def __del__(self, destroy=_pathlib.delete_tctrl):
        try:
            if self.thisown: destroy(self)
        except: pass


class tctrlPtr(tctrl):
    def __init__(self, this):
        _swig_setattr(self, tctrl, 'this', this)
        if not hasattr(self,"thisown"): _swig_setattr(self, tctrl, 'thisown', 0)
        _swig_setattr(self, tctrl,self.__class__,tctrl)
_pathlib.tctrl_swigregister(tctrlPtr)
OneSec = cvar.OneSec

class stats(_object):
    __swig_setmethods__ = {}
    __setattr__ = lambda self, name, value: _swig_setattr(self, stats, name, value)
    __swig_getmethods__ = {}
    __getattr__ = lambda self, name: _swig_getattr(self, stats, name)
    def __repr__(self):
        return "<%s.%s; proxy of C stats instance at %s>" % (self.__class__.__module__, self.__class__.__name__, self.this,)
    __swig_setmethods__["tc"] = _pathlib.stats_tc_set
    __swig_getmethods__["tc"] = _pathlib.stats_tc_get
    if _newclass:tc = property(_pathlib.stats_tc_get, _pathlib.stats_tc_set)
    __swig_setmethods__["snap"] = _pathlib.stats_snap_set
    __swig_getmethods__["snap"] = _pathlib.stats_snap_get
    if _newclass:snap = property(_pathlib.stats_snap_get, _pathlib.stats_snap_set)
    def __init__(self, *args):
        _swig_setattr(self, stats, 'this', _pathlib.new_stats(*args))
        _swig_setattr(self, stats, 'thisown', 1)
    def __del__(self, destroy=_pathlib.delete_stats):
        try:
            if self.thisown: destroy(self)
        except: pass


class statsPtr(stats):
    def __init__(self, this):
        _swig_setattr(self, stats, 'this', this)
        if not hasattr(self,"thisown"): _swig_setattr(self, stats, 'thisown', 0)
        _swig_setattr(self, stats,self.__class__,stats)
_pathlib.stats_swigregister(statsPtr)


watch_sample = _pathlib.watch_sample

elapsed_usec = _pathlib.elapsed_usec

stune_conn = _pathlib.stune_conn

watch_elapsed_sample = _pathlib.watch_elapsed_sample

write_web100_var = _pathlib.write_web100_var

pumpsegs = _pathlib.pumpsegs

