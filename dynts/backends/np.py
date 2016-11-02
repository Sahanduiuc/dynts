#
# TimeSeries Backend based on numpy
#
#
import numpy as np

from ..api.timeseries import TimeSeries, is_timeseries
from ..lib import Skiplist
from ..utils.section import asarray


arraytype = np.ndarray
nan = np.nan


_functions = {
    'min': 'min',
    'max': 'max',
    'mean': 'mean',
    'med': 'median',
    'sd': 'sd'
}


def days(d1, d0):
    t = d1 - d0
    return t.days + (t.seconds + 0.000001*t.microseconds)/86400.0


class Numpy(TimeSeries):
    """A timeserie based on numpy
    """
    def make(self, date, data, raw=False, **params):
        if date is not None and not raw:
            c = self.dateinverse
            date = (c(d) for d in date)
        date = asarray(date)
        self._skl = Skiplist(date)
        if date is None or not len(date):
            self._date = None
            self._data = None
        else:
            self._date = date
            data = asarray(data, self._dtype)
            if len(data.shape) == 1:
                data = data.reshape(len(data), 1)
            self._data = data

    @property
    def dtype(self):
        if self._data is None:
            return self._dtype
        else:
            return self._data.dtype

    @property
    def shape(self):
        if self._data is not None:
            return self._data.shape
        else:
            return 0, 0

    def __getitem__(self, i):
        return self._data[i]

    def values(self, desc=None):
        if self._data is not None:
            return reversed(self._data) if desc else self._data
        else:
            return ()

    def dates(self, desc=None):
        if self._date is not None:
            return reversed(self._date) if desc else self._date
        else:
            return ()

    def keys(self, desc = None):
        return self.dates(desc = desc)

    def start(self):
        if self:
            return self._date[0]

    def end(self):
        if self:
            return self._date[-1]

    def insert(self, dte, values):
        '''insert *values* at date *dte*.'''
        if len(values):
            dte = self.dateconvert(dte)
            if not self:
                self._date = np.array([dte])
                self._data = np.array([values])
            else:
                # search for the date
                index = self._skl.rank(dte)
                if index < 0:
                    # date not available
                    N = len(self._data)
                    index = -1-index
                    self._date.resize((N+1,))
                    self._data.resize((N+1, self.count()))
                    if index < N:
                        self._date[index+1:] = self._date[index:-1]
                        self._data[index+1:] = self._data[index:-1]
                self._date[index] = dte
                self._data[index] = values
            self._skl.insert(dte)

    def isregular(self):
        dates = iter(self.dates())
        d0 = next(dates)
        d1 = next(dates)
        dt = d1 - d0
        for d2 in dates:
            if d2 - d1 == dt:
                d1 = d2
                continue
            return False
        return True

    def frequency(self):
        freq = 0;
        for d1, d0 in laggeddates(self):
            freq += days(d1,d0)
        return freq/(len(self)-1)

    def window(self, start, end):
        b = self.asbtree()
        i1 = b.find_ge(start)
        i2 = b.find_le(end)
        return self.clone(self._date[i1:i2+1],
                          self._data[i1:i2+1])

    def merge(self, tserie, fill=nan, **kwargs):
        if is_timeseries(tserie):
            tserie = [tserie]
        else:
            tserie = tuple(tserie)
        alldates = set(self.dates())
        hash = self.ashash()
        namespace = self.namespace
        with_namespace = False
        for ts in tserie:
            if ts.namespace != namespace:
                with_namespace = True
                break
        thashes  = [(hash, np.array([fill]*self.count()))]
        names = self.names(with_namespace)
        for ts in tserie:
            alldates = alldates.union(ts.dates())
            names.extend(ts.names(with_namespace))
            thashes.append((ts.ashash(),np.array([fill]*ts.count())))
        hash.names = names
        stack = np.hstack
        mdt = lambda dt: stack((h.get(dt,ln) for h,ln in thashes))
        for dt in alldates:
            hash[dt] = mdt(dt)
        return hash.getts()

    def min(self, fallback = False):
        return self._data.min(0)

    def mean(self, fallback = False):
        return self._data.mean(0)

    def max(self, fallback = False):
        return self._data.max(0)

    def var(self, ddof = 0):
        return self._data.var(0, ddof = ddof)

    def log(self, name = None, **kwargs):
        v = np.log(self._data)
        name = name or composename('log',*self.names())
        return self.clone(self._date,v,name)

    def sqrt(self, name = None, **kwargs):
        v = np.sqrt(self._data)
        name = name or composename('sqrt',*self.names())
        return self.clone(self._date,v,name)

    def square(self, name = None, **kwargs):
        v = np.square(self._data)
        name = name or composename('square',*self.names())
        return self.clone(self._date,v,name)

    def delta(self, lag = 1, name = None, **kwargs):
        self.precondition(lag<len(self) and lag > 0,dynts.DyntsOutOfBound)
        v = self._data[lag:] - self._data[:-lag]
        name = name or 'delta(%s,%s)' % (self.name,lag)
        return self.clone(self._date[lag:],v,name)

    def delta2(self, lag = 1, name = None, **kwargs):
        lag2 = 2*lag
        self.precondition(lag2<len(self) and lag2 > 0,dynts.DyntsOutOfBound)
        d = self._data
        v = d[lag2:] + d[:-lag2] - 2*d[lag:-lag]
        name = name or 'delta2(%s,%s)' % (self.name,lag)
        return self.clone(self._date[lag2:],v,name)

    def logdelta(self, lag = 1, name = None, **kwargs):
        self.precondition(lag<len(self) and lag > 0,dynts.DyntsOutOfBound)
        v = np.log(self._data[lag:]/self._data[:-lag])
        name = name or 'logdelta(%s,%s)' % (self.name,lag)
        return self.clone(self._date[lag:],v,name)

    def _rollapply(self,
                   func,
                   window = 20,
                   bycolumn = True,
                   **kwargs):
        # NUMPY implementation of the rollapply function
        func = _functions.get(func,None) or func
        if bycolumn:
            return rollsingle(self, func, window = window, **kwargs)
        else:
            raise NotImplementedError

