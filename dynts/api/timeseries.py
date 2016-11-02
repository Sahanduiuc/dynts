import numpy as np

from dynts.utils import laggeddates, ashash, asbtree, asarray
from .data import Data
from . import operators
from ..exc import DyntsException, NotAvailable

nan = np.nan

ops = operators._ops
ts_bin_op = operators._handle_ts_or_scalar
object_type = np.dtype(object)


def is_timeseries(value):
    return isinstance(value, TimeSeries)


BACKENDS = {
    'zoo': 'zoo',
    'numpy': 'tsnumpy',
}


class TSmeta(type):

    def __new__(cls, name, bases, attrs):
        abstract = attrs.pop('abstract', False)
        attrs['type'] = (attrs.get('type') or name).lower()
        klass = super(TSmeta, cls).__new__(cls, name, bases, attrs)
        if not abstract:
            BACKENDS[klass.type] = klass
        return klass


class TimeSeries(Data, metaclass=TSmeta):
    '''A :class:`~.DynData` specialisation for timeseries.
    This class expose all the main functionalities of a timeseries

    .. attribute:: type

        string indicating the backend type (``zoo``, ``rmetrics``,
        ``numpy``, etc...)

    .. attribute:: shape

        tuple containing the timeseries dimensions.
    '''
    abstract = True
    default_align = 'right'
    _algorithms = {}

    def __init__(self, name='', date=None, data=None, info=None,
                 dtype=np.double, **params):
        super(TimeSeries,self).__init__(name, info)
        self._dtype = np.dtype(dtype)
        self.make(date, data, **params)

    __add__ = operators.add
    __sub__ = operators.sub
    __mul__ = operators.mul
    __div__ = operators.div
    __truediv__ = operators.div # Python 3

    @property
    def dtype(self):
        return self._dtype

    @property
    def is_object(self):
        '''This property is ``True`` when the timeseries contains objects'''
        return self.dtype == object_type

    def getalgo(self, operation, name):
        '''Return the algorithm for *operation* named *name*'''
        if operation not in self._algorithms:
            raise NotAvailable('{0} not registered.'.format(operation))
        oper = self._algorithms[operation]
        try:
            return oper[name]
        except KeyError:
            raise NotAvailable('{0} algorithm {1} not registered.'\
                               .format(operation,name))

    @classmethod
    def register_algorithm(cls, operation, name, callable):
        if hasattr(callable,'__call__'):
            algorithms = cls._algorithms
            if operation not in algorithms:
                algorithms[operation] = {}
            oper = algorithms[operation]
            oper[name] = callable

    ######################################################################
    # METADATA FUNCTIONS
    ######################################################################

    def __len__(self):
        return self.shape[0]

    def count(self):
        '''Number of series in timeseries.'''
        return self.shape[1]

    def dates(self, desc=None):
        '''Returns an iterable over ``datetime.date`` instances
in the timeseries.'''
        c = self.dateinverse
        for key in self.keys(desc=desc):
            yield c(key)

    def keys(self, desc = None):
        '''Returns an iterable over ``raw`` keys. The keys may be different
from dates for same backend implementations.'''
        raise NotImplementedError

    def values(self, desc=None):
        '''Returns a ``numpy.ndarray`` containing the values of the timeseries.
Implementations should try not to copy data if possible. This function
can be used to access the timeseries as if it was a matrix.'''
        raise NotImplementedError

    def items(self, desc=None, start_value=None, shift_by=None):
        '''Returns a python ``generator`` which can be used to iterate over
:func:`dynts.TimeSeries.dates` and :func:`dynts.TimeSeries.values`
returning a two dimensional
tuple ``(date,value)`` in each iteration. Similar to the python dictionary items
function.

:parameter desc: if ``True`` the iteratioon starts from the more recent data
    and proceeds backwards.
:parameter shift_by: optional parallel shift in values.
:parameter start_value: optional start value of timeseries.
'''
        if self:
            if shift_by is None and start_value is not None:
                for cross in self.values():
                    missings = 0
                    if shift_by is None:
                        shift_by = []
                        for v in cross:
                            shift_by.append(start_value - v)
                            if v != v:
                                missings += 1
                    else:
                        for j in range(len(shift_by)):
                            s = shift_by[j]
                            v = cross[j]
                            if s != s:
                                if v == v:
                                    shift_by[j] = start_value - v
                                else:
                                    missings += 1
                    if not missings:
                        break
            if shift_by:
                for d, v in zip(self.dates(desc=desc),self.values(desc=desc)):
                    yield d, v + shift_by
            else:
                for d, v in zip(self.dates(desc=desc),self.values(desc=desc)):
                    yield d, v

    def series(self):
        '''Generator of single series data (no dates are included).'''
        data = self.values()
        if len(data):
            for c in range(self.count()):
                yield data[:,c]
        else:
            raise StopIteration

    def named_series(self, ordering=None):
        '''Generator of tuples with name and serie data.'''
        series = self.series()
        if ordering:
            series = list(series)
            todo = dict(((n, idx) for idx, n in enumerate(self.names())))
            for name in ordering:
                if name in todo:
                    idx = todo.pop(name)
                    yield name, series[idx]
            for name in todo:
                idx = todo[name]
                yield name, series[idx]
        else:
            for name_serie in zip(self.names(), series):
                yield name_serie

    def serie(self, index):
        return self.values()[:,index]

    def display(self):
        for d,v in self.items():
            print('%s: %s' % (d,v))

    ######################################################################
    # OTHER REPRESENTATIONS of TIMESERIE
    ######################################################################

    def asbtree(self):
        '''Return an instance of :class:`dynts.utils.wrappers.asbtree`
which exposes binary tree like functionalities of ``self``.'''
        return asbtree(self)

    def ashash(self):
        '''Return an instance of :class:`dynts.utils.wrappers.ashash`
which exposes hash-table like functionalities of ``self``.'''
        return ashash(self)

    # DATE OPERATORS

    def dateconvert(self, dte):
        return dte

    def dateinverse(self, key):
        return key

    ######################################################################
    # OPERATIONS WHICH MODIFY TIMESERIES
    ######################################################################

    def insert(self, dte, value):
        '''Insert a new date-value pair at the end of the timeseries.'''
        raise NotImplementedError


    ######################################################################
    # OPERATIONS RETURNING NEW SERIES
    ######################################################################

    def window(self, start, end):
        raise NotImplementedError

    def merge(self, ts, all=True):
        '''Merge this :class:`TimeSeries` with one or more :class:`TimeSeries`
and return a new one.'''
        raise NotImplementedError

    def clone(self, date=None, data=None, name=None):
        '''Create a clone of timeseries'''
        name = name or self.name
        data = data if data is not None else self.values()
        ts = self.__class__(name)
        ts._dtype = self._dtype
        if date is None:
            # dates not provided
            ts.make(self.keys(), data, raw=True)
        else:
            ts.make(date, data)
        return ts

    def reduce(self, size, method = 'simple', **kwargs):
        '''Trim :class:`Timeseries` to a new *size* using the algorithm
*method*. If *size* is greater or equal than len(self) it does nothing.'''
        if size >= len(self):
            return self
        return self.getalgo('reduce',method)(self,size,**kwargs)

    def clean(self, algorithm=None):
        '''Create a new :class:`TimeSeries` with missing data removed or
replaced by the *algorithm* provided'''
        # all dates
        original_dates = list(self.dates())
        series = []
        all_dates = set()
        for serie in self.series():
            dstart, dend, vend = None, None, None
            new_dates = []
            new_values = []
            missings = []
            values = {}
            for d, v in zip(original_dates, serie):
                if v == v:
                    if dstart is None:
                        dstart = d
                    if missings:
                        for dx, vx in algorithm(dend, vend, d, v, missings):
                            new_dates.append(dx)
                            new_values.append(vx)
                        missings = []
                    dend = d
                    vend = v
                    values[d] = v
                elif dstart is not None and algorithm:
                    missings.append((dt, v))
            if missings:
                for dx, vx in algorithm(dend, vend, None, None, missings):
                    new_dates.append(dx)
                    new_values.append(vx)
                    dend = dx
            series.append((dstart, dend, values))
            all_dates = all_dates.union(values)
        cdate = []
        cdata = []
        for dt in sorted(all_dates):
            cross = []
            for start, end, values in series:
                if start is None or (dt >= start and dt <= end):
                    value = values.get(dt)
                    if value is None:
                        cross = None
                        break
                else:
                    value = nan
                cross.append(value)
            if cross:
                cdate.append(dt)
                cdata.append(cross)
        return self.clone(date=cdate, data=cdata)

    ######################################################################
    # SCALAR STANDARD FUNCTIONS
    ######################################################################

    def max(self, fallback = False):
        '''Max values by series'''
        return asarray(self.apply('max', fallback = fallback)[0])

    def min(self, fallback = False):
        '''Max values by series'''
        return asarray(self.apply('min', fallback = fallback)[0])

    def mean(self, fallback = False):
        '''Mean values by series'''
        return asarray(self.apply('mean', fallback = fallback)[0])

    def median(self, fallback = False):
        '''Median values by series. A median value of a serie
is defined as the the numeric value separating the higher half,
from the lower half. It is therefore differnt from the :meth:`TimeSeries.mean` value.

The median of a finite list of numbers can be found by arranging all the
observations from lowest value to highest value and picking the middle one.

If there is an even number of observations, then there is no single middle value;
the median is then usually defined to be the mean of the two middle values'''
        return asarray(self.apply('median', fallback = fallback)[0])

    def returns(self, fallback = False):
        '''Calculate returns as delta(log(self)) by series'''
        return self.logdelta(fallback = fallback)

    def isconsistent(self):
        '''Check if the timeseries is consistent'''
        for dt1,dt0 in laggeddates(self):
            if dt1 <= dt0:
                return False
        return True

    # PURE VIRTUAL FUNCTIONS

    def start(self):
        '''Start date of timeseries'''
        raise NotImplementedError

    def end(self):
        '''End date of timeseries'''
        raise NotImplementedError

    def frequency(self):
        '''Average frequency of dates'''
        raise NotImplementedError

    @property
    def shape(self):
        '''The dimensions of the timeseries. This is a two-elements tuple of integers
        indicating the size of the timeseries and the number of series.
        A timeseries with 2 series of length 250 will return the tuple::

            (250,2)
        '''
        raise NotImplementedError

    def __getitem__(self, i):
        raise NotImplementedError

    def colnames(self):
        raise NotImplementedError

    def delta(self, lag=1, **kwargs):
        '''\
First order derivative. Optimised.

:parameter lag: backward lag
'''
        raise NotImplementedError

    def delta2(self, lag = 2, **kwargs):
        '''\
Second order derivative. Optimised.

:parameter lag: backward lag
'''
        raise NotImplementedError

    def lag(self, lag = 1):
        raise NotImplementedError

    def log(self):
        raise NotImplementedError

    def sqrt(self):
        raise NotImplementedError

    def square(self):
        raise NotImplementedError

    def logdelta(self, lag = 1, **kwargs):
        '''Delta in log-space. Used for percentage changes.'''
        raise NotImplementedError

    def var(self, ddof = 0):
        '''Calculate variance of timeseries. Return a vector containing
the variances of each series in the timeseries.

:parameter ddof: delta degree of freedom, the divisor used in the calculation
                 is given by ``N - ddof`` where ``N`` represents the length
                 of timeseries. Default ``0``.

.. math::

    var = \\frac{\\sum_i^N (x - \\mu)^2}{N-ddof}
    '''
        N = len(self)
        if N:
            v = self.values()
            mu = sum(v)
            return (sum(v*v) - mu*mu/N)/(N-ddof)
        else:
            return None

    def sd(self):
        '''Calculate standard deviation of timeseries'''
        v = self.var()
        if len(v):
            return np.sqrt(v)
        else:
            return None

    def apply(self, func,
              window = None,
              bycolumn = True,
              align = None,
              **kwargs):
        '''Apply function ``func`` to the timeseries.

    :keyword func: string indicating function to apply
    :keyword window: Rolling window, If not defined ``func`` is applied on
                     the whole dataset. Default ``None``.
    :keyword bycolumn: If ``True``, function ``func`` is applied on
                       each column separately. Default ``True``.
    :keyword align: string specifying whether the index of the result should be ``left`` or
                    ``right`` (default) or ``centered`` aligned compared to the
                    rolling window of observations.
    :keyword kwargs: dictionary of auxiliary parameters used by function ``func``.'''
        N = len(self)
        window = window or N
        self.precondition(window<=N and window > 0,DyntsOutOfBound)
        return self._rollapply(func,
                               window = window,
                               align = align or self.default_align,
                               bycolumn = bycolumn,
                               **kwargs)

    def rollapply(self, func, window = 20, **kwargs):
        '''A generic :ref:`rolling function <rolling-function>` for function *func*.
Same construct as :meth:`dynts.TimeSeries.apply` but with default ``window`` set to ``20``.'''
        return self.apply(func, window=window, **kwargs)

    def rollmax(self, **kwargs):
        '''A :ref:`rolling function <rolling-function>` for max values.
Same as::

    self.rollapply('max',**kwargs)'''
        return self.rollapply('max',**kwargs)

    def rollmin(self, **kwargs):
        '''A :ref:`rolling function <rolling-function>` for min values.
Same as::

    self.rollapply('min',**kwargs)'''
        return self.rollapply('min',**kwargs)

    def rollmedian(self, **kwargs):
        '''A :ref:`rolling function <rolling-function>` for median values.
Same as::

    self.rollapply('median',**kwargs)'''
        return self.rollapply('median',**kwargs)

    def rollmean(self, **kwargs):
        '''A :ref:`rolling function <rolling-function>` for mean values:
Same as::

    self.rollapply('mean',**kwargs)'''
        return self.rollapply('mean',**kwargs)

    def rollsd(self, scale = 1, **kwargs):
        '''A :ref:`rolling function <rolling-function>` for stadard-deviation values:
Same as::

    self.rollapply('sd',**kwargs)'''
        ts = self.rollapply('sd',**kwargs)
        if scale != 1:
            ts *= scale
        return ts

    # INTERNALS
    ################################################################

    def makename(self, func, window = None, **kwargs):
        if window == len(self) or not window:
            return '%s(%s)' % (func,self.name)
        else:
            return '%s(%s,window=%s)' % (func,self.name,window)

    def _rollapply(func, window = 20, **kwargs):
        raise NotImplementedError

    def make(self, date, data, **kwargs):
        '''Internal function to create the inner data:

* *date* iterable/iterator/generator over dates
* *data* iterable/iterator/generator over values'''
        raise NotImplementedError

    def precondition(self, precond, errorclass=None, msg=''):
        if not precond:
            raise (errorclass or DyntsException)(msg)
