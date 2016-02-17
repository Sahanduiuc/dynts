import matplotlib.pyplot as plt


def toplot(ts,
           filename=None,
           grid=True,
           legend=True,
           pargs=(),
           **kwargs):
    '''To plot formatter'''
    fig = plt.figure()
    ax = fig.add_subplot(111)
    dates = list(ts.dates())
    ax.plot(dates, ts.values(), *pargs)
    ax.grid(grid)

    # rotates and right aligns the x labels, and moves the bottom of the
    # axes up to make room for them
    fig.autofmt_xdate()

    # add legend or title
    names = ts.name.split('__')
    if len(names) == 1:
        title = names[0]
        fontweight = kwargs.get('title_fontweight', 'bold')
        ax.set_title(title, fontweight=fontweight)#,fontsize=fontsize,
    elif legend:
        ##add legend
        loc = kwargs.get('legend_location','best')
        ncol = kwargs.get('legend_ncol', 2)
        ax.legend(names, loc=loc, ncol=ncol)

    return plt
