""" plots / visualizations / figures """

import itertools
import logging
from pathlib import Path
import subprocess
import tempfile
import warnings

import h5py
import hsluv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import lines
from matplotlib import patches
from matplotlib import ticker
from scipy import special
from scipy.interpolate import PchipInterpolator
from sklearn.decomposition import PCA
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process import kernels
from sklearn.mixture import GaussianMixture

from . import workdir, systems, parse_system, expt, model, mcmc
from .design import Design
from .emulator import emulators


fontsmall, fontnormal, fontlarge = 5, 6, 7
offblack = '#262626'
aspect = 1/1.618
resolution = 72.27
textwidth = 307.28987/resolution
textheight = 261.39864/resolution
fullwidth = 350/resolution
fullheight = 270/resolution

plt.rcdefaults()
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Lato'],
    'mathtext.fontset': 'custom',
    'mathtext.default': 'it',
    'mathtext.rm': 'sans',
    'mathtext.it': 'sans:italic:medium',
    'mathtext.cal': 'sans',
    'font.size': fontnormal,
    'legend.fontsize': fontnormal,
    'axes.labelsize': fontnormal,
    'axes.titlesize': fontlarge,
    'xtick.labelsize': fontsmall,
    'ytick.labelsize': fontsmall,
    'font.weight': 400,
    'axes.labelweight': 400,
    'axes.titleweight': 400,
    'lines.linewidth': .5,
    'lines.markersize': 3,
    'lines.markeredgewidth': 0,
    'patch.linewidth': .5,
    'axes.linewidth': .4,
    'xtick.major.width': .4,
    'ytick.major.width': .4,
    'xtick.minor.width': .4,
    'ytick.minor.width': .4,
    'xtick.major.size': 1.2,
    'ytick.major.size': 1.2,
    'xtick.minor.size': .8,
    'ytick.minor.size': .8,
    'xtick.major.pad': 1.5,
    'ytick.major.pad': 1.5,
    'axes.formatter.limits': (-5, 5),
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.labelpad': 3,
    'text.color': offblack,
    'axes.edgecolor': offblack,
    'axes.labelcolor': offblack,
    'xtick.color': offblack,
    'ytick.color': offblack,
    'legend.numpoints': 1,
    'legend.scatterpoints': 1,
    'legend.frameon': False,
    'image.cmap': 'Blues',
    'image.interpolation': 'none',
    'pdf.fonttype': 42
})


plotdir = workdir / 'plots'
plotdir.mkdir(exist_ok=True)

plot_functions = {}


def plot(f):
    """
    Plot function decorator.  Calls the function, does several generic tasks,
    and saves the figure as the function name.

    """
    def wrapper(*args, **kwargs):
        logging.info('generating plot: %s', f.__name__)
        f(*args, **kwargs)

        fig = plt.gcf()

        if not fig.get_tight_layout():
            set_tight(fig)

        plotfile = plotdir / '{}.pdf'.format(f.__name__)
        fig.savefig(str(plotfile))
        logging.info('wrote %s', plotfile)
        plt.close(fig)

    plot_functions[f.__name__] = wrapper

    return wrapper


def set_tight(fig=None, **kwargs):
    """
    Set tight_layout with a better default pad.

    """
    if fig is None:
        fig = plt.gcf()

    kwargs.setdefault('pad', .1)
    fig.set_tight_layout(kwargs)


def auto_ticks(ax, axis='both', minor=False, **kwargs):
    """
    Convenient interface to matplotlib.ticker locators.

    """
    axis_list = []

    if axis in {'x', 'both'}:
        axis_list.append(ax.xaxis)
    if axis in {'y', 'both'}:
        axis_list.append(ax.yaxis)

    for axis in axis_list:
        axis.get_major_locator().set_params(**kwargs)
        if minor:
            axis.set_minor_locator(ticker.AutoMinorLocator(minor))


def format_system(system):
    """
    Format a system string into a display name, e.g.:

    >>> format_system('PbPb2760')
    'Pb+Pb 2.76 TeV'

    >>> format_system('AuAu200')
    'Au+Au 200 GeV'

    """
    proj, energy = parse_system(system)

    if energy > 1000:
        energy /= 1000
        prefix = 'T'
    else:
        prefix = 'G'

    return '{} {} {}eV'.format('+'.join(proj), energy, prefix)


def darken(rgb, amount=.5):
    """
    Darken a color by the given amount in HSLuv space.

    """
    h, s, l = hsluv.rgb_to_hsluv(rgb)
    return hsluv.hsluv_to_rgb((h, s, (1 - amount)*l))


def obs_color_hsluv(obs, subobs):
    """
    Return a nice color for the given observable in HSLuv space.
    Use obs_color() to obtain an RGB color.

    """
    if obs in {'dNch_deta', 'pT_fluct'}:
        return 250, 90, 55

    if obs == 'dET_deta':
        return 10, 65, 55

    if obs in {'dN_dy', 'mean_pT'}:
        return dict(
            pion=(210, 85, 70),
            kaon=(130, 88, 68),
            proton=(30, 90, 62),
        )[subobs]

    if obs == 'vnk':
        return {
            (2, 2): (230, 90, 65),
            (2, 4): (262, 80, 63),
            (3, 2): (150, 90, 67),
            (4, 2): (310, 70, 50),
        }[subobs]

    raise ValueError('unknown observable: {} {}'.format(obs, subobs))


def obs_color(obs, subobs):
    """
    Return a nice color for the given observable.

    """
    return hsluv.hsluv_to_rgb(obs_color_hsluv(obs, subobs))


def _observables_plots():
    """
    Metadata for observables plots.

    """
    def id_parts_plots(obs):
        return [(obs, species, dict(label=label)) for species, label in [
            ('pion', '$\pi$'), ('kaon', '$K$'), ('proton', '$p$')
        ]]

    return [
        dict(
            title='Yields',
            ylabel=(
                r'$dN_\mathrm{ch}/d\eta,\ dN/dy,\ dE_T/d\eta\ [\mathrm{GeV}]$'
            ),
            ylim=(1, 1e5),
            yscale='log',
            height_ratio=1.5,
            subplots=[
                ('dNch_deta', None, dict(label=r'$N_\mathrm{ch}$', scale=25)),
                ('dET_deta', None, dict(label=r'$E_T$', scale=5)),
                *id_parts_plots('dN_dy')
            ]
        ),
        dict(
            title='Mean $p_T$',
            ylabel=r'$\langle p_T \rangle$ [GeV]',
            ylim=(0, 1.7),
            subplots=id_parts_plots('mean_pT')
        ),
        dict(
            title='Mean $p_T$ fluctuations',
            ylabel=r'$\delta p_T/\langle p_T \rangle$',
            ylim=(0, .04),
            subplots=[('pT_fluct', None, dict())]
        ),
        dict(
            title='Flow cumulants',
            ylabel=r'$v_n\{2\}$',
            ylim=(0, .12),
            subplots=[
                ('vnk', (n, 2), dict(label='$v_{}$'.format(n)))
                for n in [2, 3, 4]
            ]
        )
    ]


def _observables(posterior=False):
    """
    Model observables at all design points or drawn from the posterior with
    experimental data points.

    """
    plots = _observables_plots()

    fig, axes = plt.subplots(
        nrows=len(plots), ncols=len(systems),
        figsize=(.8*fullwidth, fullwidth),
        gridspec_kw=dict(
            height_ratios=[p.get('height_ratio', 1) for p in plots]
        )
    )

    if posterior:
        samples = mcmc.Chain().samples(100)

    for (plot, system), ax in zip(
            itertools.product(plots, systems), axes.flat
    ):
        for obs, subobs, opts in plot['subplots']:
            color = obs_color(obs, subobs)
            scale = opts.get('scale')

            x = model.data[system][obs][subobs]['x']
            Y = (
                samples[system][obs][subobs]
                if posterior else
                model.data[system][obs][subobs]['Y']
            )

            if scale is not None:
                Y = Y*scale

            for y in Y:
                ax.plot(x, y, color=color, alpha=.08, lw=.3)

            if 'label' in opts:
                ax.text(
                    x[-1] + 3,
                    np.median(Y[:, -1]),
                    opts['label'],
                    color=darken(color), ha='left', va='center'
                )

            try:
                dset = expt.data[system][obs][subobs]
            except KeyError:
                continue

            x = dset['x']
            y = dset['y']
            yerr = np.sqrt(sum(
                e**2 for e in dset['yerr'].values()
            ))

            if scale is not None:
                y = y*scale
                yerr = yerr*scale

            ax.errorbar(
                x, y, yerr=yerr, fmt='o', ms=1.7,
                capsize=0, color='.25', zorder=1000
            )

        if plot.get('yscale') == 'log':
            ax.set_yscale('log')
            ax.minorticks_off()
        else:
            auto_ticks(ax, 'y', nbins=4, minor=2)

        ax.set_xlim(0, 80)
        auto_ticks(ax, 'x', nbins=5, minor=2)

        ax.set_ylim(plot['ylim'])

        if ax.is_first_row():
            ax.set_title(format_system(system))
        elif ax.is_last_row():
            ax.set_xlabel('Centrality %')

        if ax.is_first_col():
            ax.set_ylabel(plot['ylabel'])

        if ax.is_last_col():
            ax.text(
                1.02, .5, plot['title'],
                transform=ax.transAxes, ha='left', va='center',
                size=plt.rcParams['axes.labelsize'], rotation=-90
            )

    set_tight(fig, rect=[0, 0, .97, 1])


@plot
def observables_design():
    _observables(posterior=False)


@plot
def observables_posterior():
    _observables(posterior=True)


@plot
def observables_map():
    """
    Model observables and ratio to experiment at the maximum a posteriori
    (MAP) estimate.

    """
    plots = _observables_plots()

    ylim = {
        'Yields': (2, 1e5),
        'Flow cumulants': (0, .15),
        'Mean $p_T$': (0, 1.7),
        'Mean $p_T$ fluctuations': (0, .045),
    }

    for n, p in enumerate(plots):
        p['ylim'] = ylim[p['title']]
        if p['title'] == 'Flow cumulants':
            move_index = n
            p.update(
                ylabel=r'$v_n\{k\}$',
                subplots=[
                    ('vnk', nk, dict(label='$v_{}\{{{}\}}$'.format(*nk)))
                    for nk in [(2, 2), (2, 4), (3, 2), (4, 2)]
                ],
                legend=True
            )

    plots.insert(1, plots.pop(move_index))

    ncols = int(len(plots)/2)

    fig, axes = plt.subplots(
        nrows=4, ncols=ncols,
        figsize=(.8*fullwidth, .4*ncols*fullwidth),
        gridspec_kw=dict(
            height_ratios=list(itertools.chain.from_iterable(
                (p.get('height_ratio', 1), .4) for p in plots[::ncols]
            ))
        )
    )

    labels = {}
    handles = dict(expt={}, model={})

    for plot, ax, ratio_ax in zip(plots, axes[::2].flat, axes[1::2].flat):
        for system, (obs, subobs, opts) in itertools.product(
                systems, plot['subplots']
        ):
            color = obs_color(obs, subobs)
            scale = opts.get('scale')

            linestyle, fill_markers = {
                'PbPb2760': ('solid', True),
                'PbPb5020': ('dashed', False),
            }[system]

            x = model.map_data[system][obs][subobs]['x']
            y = model.map_data[system][obs][subobs]['Y']

            if scale is not None:
                y = y*scale

            ax.plot(x, y, color=color, ls=linestyle)
            handles['model'][system] = \
                lines.Line2D([], [], color=offblack, ls=linestyle)

            if 'label' in opts and (obs, subobs) not in labels:
                labels[obs, subobs] = ax.text(
                    x[-1] + 3, y[-1],
                    opts['label'],
                    color=darken(color), ha='left', va='center'
                )

            try:
                dset = expt.data[system][obs][subobs]
            except KeyError:
                continue

            x = dset['x']
            yexp = dset['y']
            yerr = dset['yerr']
            yerrstat = yerr.get('stat')
            yerrsys = yerr.get('sys', yerr.get('sum'))

            if scale is not None:
                yexp = yexp*scale
                if yerrstat is not None:
                    yerrstat = yerrstat*scale
                if yerrsys is not None:
                    yerrsys = yerrsys*scale

            handles['expt'][system] = ax.errorbar(
                x, yexp, yerr=yerrstat, fmt='o', ms=1.7,
                capsize=0, color=offblack,
                mfc=(offblack if fill_markers else '.9'),
                mec=offblack, mew=(0 if fill_markers else .25),
                zorder=1000
            )

            ax.fill_between(
                x, yexp - yerrsys, yexp + yerrsys,
                facecolor='.9', zorder=-10,
            )

            ratio_ax.plot(x, y/yexp, color=color, ls=linestyle)

        if plot.get('yscale') == 'log':
            ax.set_yscale('log')
            ax.minorticks_off()
        else:
            auto_ticks(ax, 'y', nbins=4, minor=2)

        for a in [ax, ratio_ax]:
            a.set_xlim(0, 80)
            auto_ticks(a, 'x', nbins=5, minor=2)

        if ratio_ax.is_last_row():
            ratio_ax.set_xlabel('Centrality %')

        ax.set_ylim(plot['ylim'])
        ax.set_ylabel(plot['ylabel'])

        if plot.get('legend'):
            ax.legend(
                [handles[t][s] for t in ['model', 'expt'] for s in systems],
                [fmt.format(parse_system(s)[1]/1000)
                 for fmt in ['', '{} TeV'] for s in systems],
                ncol=2, loc='upper left', bbox_to_anchor=(0, .94),
                columnspacing=0, handletextpad=0
            )

        ax.text(
            .5, 1 if ax.is_first_row() else .97, plot['title'],
            transform=ax.transAxes, ha='center', va='top',
            size=plt.rcParams['axes.labelsize']
        )

        ratio_ax.axhline(1, lw=.5, color='0.5', zorder=-100)
        ratio_ax.axhspan(.9, 1.1, color='0.93', zorder=-200)
        ratio_ax.set_ylim(.85, 1.15)
        ratio_ax.set_ylabel('Ratio')
        ratio_ax.text(
            ratio_ax.get_xlim()[1], .9, '±10%',
            color='.6', zorder=-50,
            ha='right', va='bottom',
            size=plt.rcParams['xtick.labelsize']
        )

    set_tight(fig)


@plot
def find_map():
    """
    Find the maximum a posteriori (MAP) point and compare emulator predictions
    to experimental data.

    """
    from scipy.optimize import minimize

    chain = mcmc.Chain()

    fixed_params = {
        'trento_p': 0.,
        'etas_min': .08,
        'etas_hrg': .3,
        'model_sys_err': .1,
    }

    opt_params = [k for k in chain.keys if k not in fixed_params]

    def full_x(x):
        x = dict(zip(opt_params, x), **fixed_params)
        return [x[k] for k in chain.keys]

    res = minimize(
        lambda x: -chain.log_posterior(full_x(x))[0],
        x0=np.median(chain.load(*opt_params, thin=1000), axis=0),
        tol=1e-8,
        bounds=[
            (a + 1e-6*(b - a), b - 1e-6*(b - a))
            for (a, b), k in zip(chain.range, chain.keys)
            if k in opt_params
        ]
    )

    logging.debug('optimization result:\n%s', res)
    width = max(map(len, chain.keys)) + 2
    logging.info(
        'MAP params:\n%s',
        '\n'.join(
            k.ljust(width) + str(x) for k, x in zip(chain.keys, full_x(res.x))
        )
    )

    pred = chain._predict(np.atleast_2d(full_x(res.x)))

    plots = _observables_plots()

    fig, axes = plt.subplots(
        nrows=2*len(plots), ncols=len(systems),
        figsize=(.8*fullwidth, 1.4*fullwidth),
        gridspec_kw=dict(
            height_ratios=list(itertools.chain.from_iterable(
                (p.get('height_ratio', 1), .4) for p in plots
            ))
        )
    )

    for (plot, system), ax, ratio_ax in zip(
            itertools.product(plots, systems), axes[::2].flat, axes[1::2].flat
    ):
        for obs, subobs, opts in plot['subplots']:
            color = obs_color(obs, subobs)
            scale = opts.get('scale')

            x = model.data[system][obs][subobs]['x']
            y = pred[system][obs][subobs][0]

            if scale is not None:
                y = y*scale

            ax.plot(x, y, color=color)

            if 'label' in opts:
                ax.text(
                    x[-1] + 3, y[-1],
                    opts['label'],
                    color=darken(color), ha='left', va='center'
                )

            try:
                dset = expt.data[system][obs][subobs]
            except KeyError:
                continue

            x = dset['x']
            yexp = dset['y']
            yerr = dset['yerr']
            yerrstat = yerr.get('stat')
            yerrsys = yerr.get('sys', yerr.get('sum'))

            if scale is not None:
                yexp = yexp*scale
                if yerrstat is not None:
                    yerrstat = yerrstat*scale
                if yerrsys is not None:
                    yerrsys = yerrsys*scale

            ax.errorbar(
                x, yexp, yerr=yerrstat, fmt='o', ms=1.7,
                capsize=0, color='.25', zorder=1000
            )

            ax.fill_between(
                x, yexp - yerrsys, yexp + yerrsys,
                color='.9', zorder=-10
            )

            ratio_ax.plot(x, y/yexp, color=color)

        if plot.get('yscale') == 'log':
            ax.set_yscale('log')
            ax.minorticks_off()
        else:
            auto_ticks(ax, 'y', nbins=4, minor=2)

        for a in [ax, ratio_ax]:
            a.set_xlim(0, 80)
            auto_ticks(a, 'x', nbins=5, minor=2)

        ax.set_xticklabels([])

        ax.set_ylim(plot['ylim'])

        if ax.is_first_row():
            ax.set_title(format_system(system))
        elif ax.is_last_row():
            ax.set_xlabel('Centrality %')

        if ax.is_first_col():
            ax.set_ylabel(plot['ylabel'])

        if ax.is_last_col():
            ax.text(
                1.02, .5, plot['title'],
                transform=ax.transAxes, ha='left', va='center',
                size=plt.rcParams['axes.labelsize'], rotation=-90
            )

        ratio_ax.axhline(1, lw=.5, color='0.5', zorder=-100)
        ratio_ax.axhspan(0.9, 1.1, color='0.95', zorder=-200)
        ratio_ax.set_ylim(0.8, 1.2)
        ratio_ax.set_yticks(np.arange(80, 121, 20)/100)
        ratio_ax.set_ylabel('Ratio')

    set_tight(fig, rect=[0, 0, .97, 1])


def format_ci(samples, ci=.9):
    """
    Compute the median and a credible interval for an array of samples and
    return a TeX-formatted string.

    """
    cil, cih = mcmc.credible_interval(samples, ci=ci)
    median = np.median(samples)
    ul = median - cil
    uh = cih - median

    # decide precision for formatting numbers
    # this is NOT general but it works for the present data
    if abs(median) < .2 and ul < .02:
        precision = 3
    elif abs(median) < 1:
        precision = 2
    else:
        precision = 1

    fmt = str(precision).join(['{:#.', 'f}'])

    return ''.join([
        '$', fmt.format(median),
        '_{-', fmt.format(ul), '}',
        '^{+', fmt.format(uh), '}$'
    ])


def _posterior(
        params=None, ignore=None,
        scale=1, padr=.99, padt=.98,
        cmap=None
):
    """
    Triangle plot of posterior marginal and joint distributions.

    """
    chain = mcmc.Chain()

    if params is None and ignore is None:
        params = set(chain.keys)
    elif params is not None:
        params = set(params)
    elif ignore is not None:
        params = set(chain.keys) - set(ignore)

    keys, labels, ranges = map(list, zip(*(
        i for i in zip(chain.keys, chain.labels, chain.range)
        if i[0] in params
    )))
    ndim = len(params)

    data = chain.load(*keys).T

    cmap = plt.get_cmap(cmap)
    cmap.set_bad('white')

    line_color = cmap(.8)
    fill_color = cmap(.5, alpha=.1)

    fig, axes = plt.subplots(
        nrows=ndim, ncols=ndim,
        sharex='col', sharey='row',
        figsize=2*(scale*fullheight,)
    )

    for samples, key, lim, ax in zip(data, keys, ranges, axes.diagonal()):
        counts, edges = np.histogram(samples, bins=50, range=lim)
        x = (edges[1:] + edges[:-1]) / 2
        y = .85 * (lim[1] - lim[0]) * counts / counts.max() + lim[0]
        # smooth histogram with monotonic cubic interpolation
        interp = PchipInterpolator(x, y)
        x = np.linspace(x[0], x[-1], 10*x.size)
        y = interp(x)
        ax.plot(x, y, lw=.5, color=line_color)
        ax.fill_between(x, lim[0], y, color=fill_color, zorder=-10)

        ax.set_xlim(lim)
        ax.set_ylim(lim)

        if key == 'dmin3':
            samples = samples**(1/3)

        ax.annotate(
            format_ci(samples), (.62, .92), xycoords='axes fraction',
            ha='center', va='bottom', fontsize=4.5
        )

    for ny, nx in zip(*np.tril_indices_from(axes, k=-1)):
        axes[ny][nx].hist2d(
            data[nx], data[ny], bins=100,
            range=(ranges[nx], ranges[ny]),
            cmap=cmap, cmin=1
        )
        axes[nx][ny].set_axis_off()

    for key, label, axb, axl in zip(keys, labels, axes[-1], axes[:, 0]):
        for axis in [axb.xaxis, axl.yaxis]:
            axis.set_label_text(label.replace(r'\ [', '$\n$['), fontsize=4)
            axis.set_tick_params(labelsize=3)
            if key == 'dmin3':
                ticks = [0., 1.2, 1.5, 1.7]
                axis.set_ticklabels(list(map(str, ticks)))
                axis.set_ticks([t**3 for t in ticks])
            else:
                axis.set_major_locator(ticker.LinearLocator(3))
                if (
                        axis.axis_name == 'x'
                        and scale / ndim < .13
                        and any(len(str(x)) > 4 for x in axis.get_ticklocs())
                ):
                    for t in axis.get_ticklabels():
                        t.set_rotation(30)

        axb.get_xticklabels()[0].set_horizontalalignment('left')
        axb.get_xticklabels()[-1].set_horizontalalignment('right')
        axl.get_yticklabels()[0].set_verticalalignment('bottom')
        axl.get_yticklabels()[-1].set_verticalalignment('top')

    set_tight(fig, pad=.05, h_pad=.1, w_pad=.1, rect=[0., 0., padr, padt])


@plot
def posterior():
    _posterior(ignore={'etas_hrg'}, scale=1.6, padr=1., padt=.99)


@plot
def posterior_shear():
    _posterior(
        scale=.35, padt=.96, padr=1.,
        params={'etas_min', 'etas_slope', 'etas_curv'}
    )


@plot
def posterior_bulk():
    _posterior(
        scale=.3, padt=.96, padr=1.,
        params={'zetas_max', 'zetas_width'}
    )


@plot
def posterior_p():
    """
    Distribution of trento p parameter with annotations for other models.

    """
    plt.figure(figsize=(.65*textwidth, .25*textwidth))
    ax = plt.axes()

    data = mcmc.Chain().load('trento_p').ravel()

    counts, edges = np.histogram(data, bins=50)
    x = (edges[1:] + edges[:-1]) / 2
    y = counts / counts.max()
    interp = PchipInterpolator(x, y)
    x = np.linspace(x[0], x[-1], 10*x.size)
    y = interp(x)
    ax.plot(x, y, color=plt.cm.Blues(0.8))
    ax.fill_between(x, y, color=plt.cm.Blues(0.15), zorder=-10)

    ax.set_xlabel('$p$')

    for spine in ax.spines.values():
        spine.set_visible(False)

    for label, x, err in [
            ('KLN', -.67, .01),
            ('EKRT /\nIP-Glasma', 0, .1),
            ('Wounded\nnucleon', 1, None),
    ]:
        args = ([x], [0], 'o') if err is None else ([x - err, x + err], [0, 0])
        ax.plot(*args, lw=4, ms=4, color=offblack, alpha=.58, clip_on=False)

        if label.startswith('EKRT'):
            x -= .275

        ax.text(x, .05, label, va='bottom', ha='center')

    ax.text(.1, .8, format_ci(data))
    ax.set_xticks(np.arange(-10, 11, 5)/10)
    ax.set_xticks(np.arange(-75, 76, 50)/100, minor=True)

    for t in ax.get_xticklabels():
        t.set_y(-.03)

    xm = 1.2
    ax.set_xlim(-xm, xm)
    ax.add_artist(
        patches.FancyArrowPatch(
            (-xm, 0), (xm, 0),
            linewidth=.6,
            arrowstyle=patches.ArrowStyle.CurveFilledAB(
                head_length=3, head_width=1.5
            ),
            facecolor=offblack, edgecolor=offblack,
            clip_on=False, zorder=100
        )
    )

    ax.set_yticks([])
    ax.set_ylim(0, 1.01*y.max())

    set_tight(pad=0)


region_style = dict(color='.93', zorder=-100)
Tc = .154


def _region_shear(mode='full', scale=.6):
    """
    Estimate of the temperature dependence of shear viscosity eta/s.

    """
    plt.figure(figsize=(scale*textwidth, scale*aspect*textwidth))
    ax = plt.axes()

    def etas(T, m=0, s=0, c=0):
        return m + s*(T - Tc)*(T/Tc)**c

    chain = mcmc.Chain()

    rangedict = dict(zip(chain.keys, chain.range))
    ekeys = ['etas_' + k for k in ['min', 'slope', 'curv']]

    T = np.linspace(Tc, .3, 100)

    prior = ax.fill_between(
        T, etas(T, *(rangedict[k][1] for k in ekeys)),
        **region_style
    )

    ax.set_xlim(xmin=.15)
    ax.set_ylim(0, .6)
    ax.set_xticks(np.arange(150, 301, 50)/1000)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(2))
    auto_ticks(ax, 'y', minor=2)

    ax.set_xlabel('Temperature [GeV]')
    ax.set_ylabel(r'$\eta/s$')

    if mode == 'empty':
        return

    if mode == 'examples':
        for args in [
                (.05, 1.0, -1),
                (.10, 1.7, 0),
                (.15, 2.0, 1),
        ]:
            ax.plot(T, etas(T, *args), color=plt.cm.Blues(.7))
        return

    eparams = chain.load(*ekeys).T
    intervals = np.array([
        mcmc.credible_interval(etas(t, *eparams))
        for t in T
    ]).T

    band = ax.fill_between(T, *intervals, color=plt.cm.Blues(.32))

    ax.plot(T, np.full_like(T, 1/(4*np.pi)), color='.6')
    ax.text(.299, .07, r'KSS bound $1/4\pi$', va='top', ha='right', color='.4')

    median, = ax.plot(
        T, etas(T, *map(np.median, eparams)),
        color=plt.cm.Blues(.77)
    )

    ax.legend(*zip(*[
        (prior, 'Prior range'),
        (median, 'Posterior median'),
        (band, '90% credible region'),
    ]), loc='upper left', bbox_to_anchor=(0, 1.03))


@plot
def region_shear():
    _region_shear()


@plot
def region_shear_empty():
    _region_shear('empty')


@plot
def region_shear_examples():
    _region_shear('examples', scale=.5)


def _region_bulk(mode='full', scale=.6):
    """
    Estimate of the temperature dependence of bulk viscosity zeta/s.

    """
    plt.figure(figsize=(scale*textwidth, scale*aspect*textwidth))
    ax = plt.axes()

    def zetas(T, zetas_max=0, zetas_width=1):
        return zetas_max / (1 + ((T - Tc)/zetas_width)**2)

    chain = mcmc.Chain()

    keys, ranges = map(list, zip(*(
        i for i in zip(chain.keys, chain.range)
        if i[0].startswith('zetas')
    )))

    T = Tc*np.linspace(.5, 1.5, 1000)

    maxdict = {k: r[1] for k, r in zip(keys, ranges)}
    ax.fill_between(
        T, zetas(T, **maxdict),
        label='Prior range',
        **region_style
    )

    ax.set_xlim(T[0], T[-1])
    ax.set_ylim(0, 1.05*maxdict['zetas_max'])
    auto_ticks(ax, minor=2)

    ax.set_xlabel('Temperature [GeV]')
    ax.set_ylabel(r'$\zeta/s$')

    if mode == 'empty':
        return

    if mode == 'examples':
        for args in [
                (.025, .01),
                (.050, .03),
                (.075, .05),
        ]:
            ax.plot(T, zetas(T, *args), color=plt.cm.Blues(.7))
        return

    # use a Gaussian mixture model to classify zeta/s parameters
    samples = chain.load(*keys, thin=10)
    gmm = GaussianMixture(n_components=3, covariance_type='full').fit(samples)
    labels = gmm.predict(samples)

    for n in range(gmm.n_components):
        params = dict(zip(
            keys,
            (mcmc.credible_interval(s)[1] for s in samples[labels == n].T)
        ))

        if params['zetas_max'] > .05:
            cmap = 'Blues'
        elif params['zetas_width'] > .03:
            cmap = 'Greens'
        else:
            cmap = 'Oranges'

        curve = zetas(T, **params)
        color = getattr(plt.cm, cmap)(.65)

        ax.plot(T, curve, color=color, zorder=-10)
        ax.fill_between(T, curve, color=color, alpha=.1, zorder=-20)

    ax.legend(loc='upper left')


@plot
def region_bulk():
    _region_bulk()


@plot
def region_bulk_empty():
    _region_bulk('empty')


@plot
def region_bulk_examples():
    _region_bulk('examples', scale=.5)


@plot
def flow_corr():
    """
    Symmetric cumulants SC(m, n) at the MAP point compared to experiment.

    """
    fig, axes = plt.subplots(
        figsize=(textwidth, .75*textwidth),
        nrows=2, ncols=2, gridspec_kw=dict(width_ratios=[2, 3])
    )

    cmapx_normal = .7
    cmapx_pred = .5
    dashes_pred = [3, 2]

    def label(*mn, normed=False):
        fmt = r'\mathrm{{SC}}({0}, {1})'
        if normed:
            fmt += r'/\langle v_{0}^2 \rangle\langle v_{1}^2 \rangle'
        return fmt.format(*mn).join('$$')

    for obs, ax in zip(
            ['sc_central', 'sc', 'sc_normed_central', 'sc_normed'],
            axes.flat
    ):
        for (mn, cmap), sys in itertools.product(
                [
                    ((4, 2), 'Blues'),
                    ((3, 2), 'Oranges'),
                ],
                systems
        ):
            x = model.map_data[sys][obs][mn]['x']
            y = model.map_data[sys][obs][mn]['Y']

            pred = obs not in expt.data[sys]
            cmapx = cmapx_pred if pred else cmapx_normal

            kwargs = {}

            if pred:
                kwargs.update(dashes=dashes_pred)

            if ax.is_first_col() and ax.is_first_row():
                fmt = '{:.2f} TeV'
                if pred:
                    fmt += ' (prediction)'
                lbl = fmt.format(parse_system(sys)[1]/1000)
                if not any(l.get_label() == lbl for l in ax.get_lines()):
                    ax.add_line(lines.Line2D(
                        [], [], color=plt.cm.Greys(cmapx),
                        label=lbl, **kwargs
                    ))
            elif ax.is_last_col() and not pred:
                kwargs.update(label=label(*mn, normed='normed' in obs))

            ax.plot(
                x, y, lw=.75,
                color=getattr(plt.cm, cmap)(cmapx),
                **kwargs
            )

            if pred:
                continue

            x = expt.data[sys][obs][mn]['x']
            y = expt.data[sys][obs][mn]['y']
            yerr = expt.data[sys][obs][mn]['yerr']

            ax.errorbar(
                x, y, yerr=yerr['stat'],
                fmt='o', ms=2, capsize=0, color='.25', zorder=100
            )

            ax.fill_between(
                x, y - yerr['sys'], y + yerr['sys'],
                color='.9', zorder=-10
            )

        ax.axhline(
            0, color='.75', lw=plt.rcParams['xtick.major.width'],
            zorder=-100
        )

        ax.set_xlim(0, 10 if 'central' in obs else 70)

        auto_ticks(ax, nbins=6, minor=2)

        ax.legend(loc='best')

        if ax.is_first_col():
            ax.set_ylabel(label('m', 'n', normed='normed' in obs))

        if ax.is_first_row():
            ax.set_title(
                'Most central collisions'
                if 'central' in obs else
                'Minimum bias'
            )
        else:
            ax.set_xlabel('Centrality %')


@plot
def flow_extra():
    """
    vn{2} in central bins and v2{4}.

    """
    plots, width_ratios = zip(*[
        (('vnk_central', 'Central two-particle cumulants', r'$v_n\{2\}$'), 2),
        (('vnk', 'Four-particle cumulants', r'$v_2\{4\}$'), 3),
    ])

    fig, axes = plt.subplots(
        figsize=(textwidth, .42*textwidth),
        ncols=len(plots), gridspec_kw=dict(width_ratios=width_ratios)
    )

    cmaps = {2: plt.cm.GnBu, 3: plt.cm.Purples}

    for (obs, title, ylabel), ax in zip(plots, axes):
        for sys, (cmapx, dashes, fmt) in zip(
                systems, [
                    (.7, (None, None), 'o'),
                    (.6, (3, 2), 's'),
                ]
        ):
            syslabel = '{:.2f} TeV'.format(parse_system(sys)[1]/1000)
            for subobs, dset in model.map_data[sys][obs].items():
                x = dset['x']
                y = dset['Y']

                ax.plot(
                    x, y,
                    color=cmaps[subobs](cmapx), dashes=dashes,
                    label='Model ' + syslabel
                )

                try:
                    dset = expt.data[sys][obs][subobs]
                except KeyError:
                    continue

                x = dset['x']
                y = dset['y']
                yerr = dset['yerr']

                ax.errorbar(
                    x, y, yerr=yerr['stat'],
                    fmt=fmt, ms=2.2, capsize=0, color='.25', zorder=100,
                    label='ALICE ' + syslabel
                )

                ax.fill_between(
                    x, y - yerr['sys'], y + yerr['sys'],
                    color='.9', zorder=-10
                )

                if obs == 'vnk_central':
                    ax.text(
                        x[-1] + .15, y[-1], '$v_{}$'.format(subobs),
                        color=cmaps[subobs](.99), ha='left', va='center'
                    )

        auto_ticks(ax, 'y', minor=2)
        ax.set_xlim(0, dset['cent'][-1][1])

        ax.set_xlabel('Centrality %')
        ax.set_ylabel(ylabel)
        ax.set_title(title)

    ax.legend(loc='lower right')


@plot
def design():
    """
    Projection of a LH design into two dimensions.

    """
    fig = plt.figure(figsize=(.5*textwidth, .5*textwidth))
    ratio = 5
    gs = plt.GridSpec(ratio + 1, ratio + 1)

    ax_j = fig.add_subplot(gs[1:, :-1])
    ax_x = fig.add_subplot(gs[0, :-1], sharex=ax_j)
    ax_y = fig.add_subplot(gs[1:, -1], sharey=ax_j)

    d = Design(systems[0])

    keys = ('etas_min', 'etas_slope')
    indices = tuple(d.keys.index(k) for k in keys)

    x, y = (d.array[:, i] for i in indices)
    ax_j.plot(x, y, 'o', color=plt.cm.Blues(0.75), mec='white', mew=.3)

    hist_kw = dict(bins=30, color=plt.cm.Blues(0.4), edgecolor='white', lw=.5)
    ax_x.hist(x, **hist_kw)
    ax_y.hist(y, orientation='horizontal', **hist_kw)

    for ax in fig.axes:
        ax.tick_params(top='off', right='off')
        spines = ['top', 'right']
        if ax is ax_x:
            spines += ['left']
        elif ax is ax_y:
            spines += ['bottom']
        for spine in spines:
            ax.spines[spine].set_visible(False)
        for ax_name in 'xaxis', 'yaxis':
            getattr(ax, ax_name).set_ticks_position('none')

    auto_ticks(ax_j)

    for ax in ax_x, ax_y:
        ax.tick_params(labelbottom='off', labelleft='off')

    for i, xy in zip(indices, 'xy'):
        for f, l in [('lim', d.range), ('label', d.labels)]:
            getattr(ax_j, 'set_{}{}'.format(xy, f))(l[i])


@plot
def gp():
    """
    Conditioning a Gaussian process.

    """
    fig, axes = plt.subplots(
        figsize=(.45*textwidth, .85*textheight),
        nrows=2, sharex='col'
    )

    def dummy_optimizer(obj_func, initial_theta, bounds):
        return initial_theta, 0.

    gp = GPR(1.*kernels.RBF(.8), optimizer=dummy_optimizer)

    def sample_y(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            return gp.sample_y(*args, **kwargs)

    x = np.linspace(0, 5, 1000)
    X = x[:, np.newaxis]

    x_train = np.linspace(.5, 4.5, 4)
    X_train = x_train[:, np.newaxis]

    for title, ax in zip(['Random functions', 'Conditioned on data'], axes):
        if title.startswith('Conditioned'):
            y = sample_y(X_train, random_state=23158).squeeze()
            y -= .5*(y.max() + y.min())
            gp.fit(X_train, y)
            training_data, = plt.plot(x_train, y, 'o', color='.3', zorder=50)

        for s, c in zip(
                sample_y(X, n_samples=4, random_state=34576).T,
                ['Blues', 'Greens', 'Oranges', 'Purples']
        ):
            ax.plot(x, s, color=getattr(plt.cm, c)(.6))

        mean, std = gp.predict(X, return_std=True)
        std = ax.fill_between(x, mean - std, mean + std, color='.92')
        mean, = ax.plot(x, mean, color='.42', dashes=(3.5, 1.5))

        ax.set_ylim(-2, 2)
        ax.set_ylabel('Output')
        auto_ticks(ax)

        ax.set_title(title, y=.9)

    ax.set_xlabel('Input')
    ax.legend(*zip(*[
        (mean, 'Mean prediction'),
        (std, 'Uncertainty'),
        (training_data, 'Training data'),
    ]), loc='lower left')

    set_tight(fig, h_pad=1)


@plot
def pca():
    fig = plt.figure(figsize=(.45*textwidth, .45*textwidth))
    ratio = 5
    gs = plt.GridSpec(ratio + 1, ratio + 1)

    ax_j = fig.add_subplot(gs[1:, :-1])
    ax_x = fig.add_subplot(gs[0, :-1], sharex=ax_j)
    ax_y = fig.add_subplot(gs[1:, -1], sharey=ax_j)

    x, y = (
        model.data['PbPb2760'][obs][subobs]['Y'][:, 3]
        for obs, subobs in [('dN_dy', 'pion'), ('vnk', (2, 2))]
    )
    xlabel = r'$dN_{\pi^\pm}/dy$'
    ylabel = r'$v_2\{2\}$'
    xlim = 0, 1500
    ylim = 0, 0.15

    cmap = plt.cm.Blues

    ax_j.plot(x, y, 'o', color=cmap(.75), mec='white', mew=.25, zorder=10)

    for d, ax, orientation in [(x, ax_x, 'vertical'), (y, ax_y, 'horizontal')]:
        ax.hist(
            d, bins=20,
            orientation=orientation, color=cmap(.4), edgecolor='white'
        )

    xy = np.column_stack([x, y])
    xymean = xy.mean(axis=0)
    xystd = xy.std(axis=0)
    xy -= xymean
    xy /= xystd
    pca = PCA().fit(xy)
    pc = (
        7 * xystd *
        pca.explained_variance_ratio_[:, np.newaxis] *
        pca.components_
    )

    for w, p in zip(pca.explained_variance_ratio_, pc):
        if np.all(p < 0):
            p *= -1
        ax_j.annotate(
            '', xymean + p, xymean, zorder=20,
            arrowprops=dict(
                arrowstyle='->', shrinkA=0, shrinkB=0,
                color=offblack, lw=.7
            )
        )
        ax_j.text(
            *(xymean + p + (.8, .002)*np.sign(p)), s='{:.0f}%'.format(100*w),
            color=offblack, ha='center', va='top' if p[1] < 0 else 'bottom',
            zorder=20
        )

    for ax in fig.axes:
        ax.tick_params(top='off', right='off')
        spines = ['top', 'right']
        if ax is ax_x:
            spines += ['left']
        elif ax is ax_y:
            spines += ['bottom']
        for spine in spines:
            ax.spines[spine].set_visible(False)
        for ax_name in 'xaxis', 'yaxis':
            getattr(ax, ax_name).set_ticks_position('none')

    for ax in ax_x, ax_y:
        ax.tick_params(labelbottom='off', labelleft='off')

    auto_ticks(ax_j)

    ax_j.set_xlim(xlim)
    ax_j.set_ylim(ylim)

    ax_j.set_xlabel(xlabel)
    ax_j.set_ylabel(ylabel)

    set_tight(pad=.1, h_pad=.3, w_pad=.3)


@plot
def trento_events():
    """
    Random trento events.

    """
    fig, axes = plt.subplots(
        nrows=3, sharex='col',
        figsize=(.28*textwidth, .85*textheight)
    )

    xymax = 8.
    xyr = [-xymax, xymax]

    with tempfile.NamedTemporaryFile(suffix='.hdf') as t:
        subprocess.run((
            'trento Pb Pb {} --quiet --b-max 12 '
            '--grid-max {} --grid-step .1 '
            '--random-seed 6347321 --output {}'
        ).format(axes.size, xymax, t.name).split())

        with h5py.File(t.name, 'r') as f:
            for dset, ax in zip(f.values(), axes):
                ax.pcolorfast(xyr, xyr, np.array(dset), cmap=plt.cm.Blues)
                ax.set_aspect('equal')
                for xy in ['x', 'y']:
                    getattr(ax, 'set_{}ticks'.format(xy))([-5, 0, 5])

    axes[-1].set_xlabel('$x$ [fm]')
    axes[1].set_ylabel('$y$ [fm]')

    set_tight(fig, h_pad=.5)


def boxplot(
        ax, percentiles, x=0, y=0, box_width=1, line_width=1,
        color=(0, 0, 0), alpha=.6, zorder=10
):
    """
    Draw a minimal boxplot.

    `percentiles` must be a np.array of five numbers:

        whisker_low, quartile_1, median, quartile_3, whisker_high

    """
    pl, q1, q2, q3, ph = percentiles + y

    # IQR box
    ax.add_patch(patches.Rectangle(
        xy=(x - .5*box_width, q1),
        width=box_width, height=(q3 - q1),
        color=color, alpha=alpha, lw=0, zorder=zorder
    ))

    # median line
    ax.plot(
        [x - .5*box_width, x + .5*box_width], 2*[q2],
        lw=line_width, solid_capstyle='butt', color=color,
        zorder=zorder + 1
    )

    # whisker lines
    for y in [[q1, pl], [q3, ph]]:
        ax.plot(
            2*[x], y, lw=line_width, solid_capstyle='butt',
            color=color, alpha=alpha, zorder=zorder
        )


@plot
def validation_all(system='PbPb2760'):
    """
    Emulator validation: normalized residuals and RMS error for each
    observable.

    """
    fig, (ax_box, ax_rms) = plt.subplots(
        nrows=2, figsize=(10, 4),
        gridspec_kw=dict(height_ratios=[1.5, 1])
    )

    index = 1
    ticks = []
    ticklabels = []

    vdata = model.validation_data[system]
    emu = emulators[system]
    mean, cov = emu.predict(
        Design(system, validation=True).array,
        return_cov=True
    )

    def label(obs, subobs):
        if obs.startswith('d') and obs.endswith('_deta'):
            return r'$d{}/d\eta$'.format(
                {'Nch': r'N_\mathrm{ch}', 'ET': r'E_T'}[obs[1:-5]])

        id_parts_labels = {'dN_dy': 'dN/dy', 'mean_pT': r'\langle p_T \rangle'}
        if obs in id_parts_labels:
            return '${}\ {}$'.format(
                id_parts_labels[obs],
                {'pion': '\pi', 'kaon': 'K', 'proton': 'p'}[subobs]
            )

        if obs == 'pT_fluct':
            return r'$\delta p_T/\langle p_T \rangle$'

        if obs == 'vnk':
            return r'$v_{}\{{{}\}}$'.format(*subobs)

    for obs, subobslist in emu.observables:
        for subobs in subobslist:
            color = obs_color(obs, subobs)

            Y = vdata[obs][subobs]['Y']
            Y_ = mean[obs][subobs]
            S_ = np.sqrt(cov[(obs, subobs), (obs, subobs)].T.diagonal())

            Z = (Y_ - Y)/S_

            for i, percentiles in enumerate(
                    np.percentile(Z, [10, 25, 50, 75, 90], axis=0).T,
                    start=index
            ):
                boxplot(ax_box, percentiles, x=i, box_width=.75, color=color)

            rms = 100*np.sqrt(np.square(Y_/Y - 1).mean(axis=0))
            ax_rms.plot(
                np.arange(index, index + rms.size), rms, 'o', color=color
            )

            ticks.append(.5*(index + i))
            ticklabels.append(label(obs, subobs))

            index = i + 2

    ax_box.set_xticks(ticks)
    ax_box.set_xticklabels(ticklabels)
    ax_box.tick_params('x', bottom=False, labelsize=plt.rcParams['font.size'])

    ax_box.set_ylim(-2.5, 2.5)
    ax_box.set_ylabel(r'Normalized residuals')

    q, p = np.sqrt(2) * special.erfinv(2*np.array([.75, .90]) - 1)
    ax_box.axhspan(-q, q, color='.85', zorder=-20)
    for s in [-1, 0, 1]:
        ax_box.axhline(s*p, color='.5', zorder=-10)

    ax_q = ax_box.twinx()
    ax_q.set_ylim(ax_box.get_ylim())
    ax_q.set_yticks([-p, -q, 0, q, p])
    ax_q.set_yticklabels([10, 25, 50, 75, 90])
    ax_q.tick_params('y', right=False)
    ax_q.set_ylabel(
        'Normal quantiles',
        fontdict=dict(rotation=-90),
        labelpad=3*plt.rcParams['axes.labelpad']
    )

    ax_rms.set_xticks([])
    ax_rms.set_yticks(np.arange(0, 16, 5))
    ax_rms.set_ylim(0, 15)
    ax_rms.set_ylabel('RMS % error')

    for y in ax_rms.get_yticks():
        ax_rms.axhline(y, color='.5', zorder=-10)

    for ax in fig.axes:
        ax.set_xlim(0, index - 1)
        ax.spines['bottom'].set_visible(False)


@plot
def validation_example(
        system='PbPb2760',
        obs='dNch_deta', subobs=None,
        label=r'$dN_\mathrm{ch}/d\eta$',
        cent=(20, 30)
):
    """
    Example of emulator validation for a single observable.  Scatterplot of
    model calculations vs emulator predictions with histogram and boxplot of
    normalized residuals.

    """
    fig, axes = plt.subplots(
        ncols=2, figsize=(4., 2.5),
        gridspec_kw=dict(width_ratios=[3, 1])
    )

    ax_scatter, ax_hist = axes

    vdata = model.validation_data[system][obs][subobs]
    cent_slc = (slice(None), vdata['cent'].index(cent))
    y = vdata['Y'][cent_slc]

    mean, cov = emulators[system].predict(
        Design(system, validation=True).array,
        return_cov=True
    )
    y_ = mean[obs][subobs][cent_slc]
    std_ = np.sqrt(cov[(obs, subobs), (obs, subobs)].T.diagonal()[cent_slc])

    color = obs_color(obs, subobs)
    alpha = .6

    ax_scatter.set_aspect('equal')
    ax_scatter.errorbar(
        y_, y, xerr=std_,
        fmt='o', ms=2.5, mew=.1, mec='white',
        color=color, alpha=alpha
    )
    dy = .03*y.ptp()
    x = [y.min() - dy, y.max() + dy]
    ax_scatter.plot(x, x, color='.4')
    ax_scatter.set_xlabel('Emulator prediction')
    ax_scatter.set_ylabel('Model calculation')
    ax_scatter.text(
        .04, .96, '{} {}–{}%'.format(label, *cent),
        horizontalalignment='left', verticalalignment='top',
        transform=ax_scatter.transAxes
    )

    zmax = 3.5
    zrange = (-zmax, zmax)

    z = (y_ - y)/std_

    ax_hist.hist(
        z, bins=30, range=zrange, normed=True,
        orientation='horizontal', color=color, alpha=alpha
    )
    x = np.linspace(-zmax, zmax, 1000)
    ax_hist.plot(np.exp(-.5*x*x)/np.sqrt(2*np.pi), x, color='.25')

    box_x = .75
    box_width = .1

    boxplot(
        ax_hist, np.percentile(z, [10, 25, 50, 75, 90]),
        x=box_x, box_width=box_width, color=color, alpha=alpha
    )

    guide_width = 2.5*box_width

    q, p = np.sqrt(2) * special.erfinv(2*np.array([.75, .90]) - 1)
    ax_hist.add_patch(patches.Rectangle(
        xy=(box_x - .5*guide_width, -q),
        width=guide_width, height=2*q,
        color='.85', zorder=-20
    ))
    for s in [-1, 0, 1]:
        ax_hist.plot(
            [box_x - .5*guide_width, box_x + .5*guide_width], 2*[s*p],
            color='.5', zorder=-10
        )

    ax_hist.set_ylim(zrange)
    ax_hist.spines['bottom'].set_visible(False)
    ax_hist.tick_params('x', bottom=False, labelbottom=False)
    ax_hist.set_ylabel('Normalized residuals')

    ax_q = ax_hist.twinx()
    ax_q.spines['bottom'].set_visible(False)
    ax_q.set_ylim(ax_hist.get_ylim())
    ax_q.set_yticks([-p, -q, 0, q, p])
    ax_q.set_yticklabels([10, 25, 50, 75, 90])
    ax_q.tick_params('y', right=False)
    ax_q.set_ylabel(
        'Normal quantiles',
        fontdict=dict(rotation=-90),
        labelpad=3*plt.rcParams['axes.labelpad']
    )


default_system = 'PbPb2760'


@plot
def diag_pca(system=default_system):
    """
    Diagnostic: histograms of principal components and scatterplots of pairs.

    """
    Y = [g.y_train_ for g in emulators[system].gps]
    n = len(Y)
    ymax = np.ceil(max(np.fabs(y).max() for y in Y))
    lim = (-ymax, ymax)

    fig, axes = plt.subplots(nrows=n, ncols=n, figsize=2*(n,))

    for y, ax in zip(Y, axes.diagonal()):
        ax.hist(y, bins=30)
        ax.set_xlim(lim)

    for ny, nx in zip(*np.tril_indices_from(axes, k=-1)):
        ax = axes[ny][nx]
        ax.scatter(Y[nx], Y[ny])
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        axes[nx][ny].set_axis_off()

    for i in range(n):
        label = 'PC {}'.format(i)
        axes[-1][i].set_xlabel(label)
        axes[i][0].set_ylabel(label)


@plot
def diag_emu(system=default_system):
    """
    Diagnostic: plots of each principal component vs each input parameter,
    overlaid by emulator predictions at several points in design space.

    """
    gps = emulators[system].gps
    nrows = len(gps)
    ncols = gps[0].X_train_.shape[1]

    w = 1.8
    fig, axes = plt.subplots(
        nrows=nrows, ncols=ncols,
        figsize=(ncols*w, .8*nrows*w)
    )

    ymax = np.ceil(max(np.fabs(g.y_train_).max() for g in gps))
    ylim = (-ymax, ymax)

    design = Design(system)

    for ny, (gp, row) in enumerate(zip(gps, axes)):
        y = gp.y_train_

        for nx, (x, label, xlim, ax) in enumerate(zip(
                gp.X_train_.T, design.labels, design.range, row
        )):
            ax.plot(x, y, 'o', ms=.8, color='.75', zorder=10)

            x = np.linspace(xlim[0], xlim[1], 100)
            X = np.empty((x.size, ncols))

            for k, r in enumerate([.2, .5, .8]):
                X[:] = r*design.min + (1 - r)*design.max
                X[:, nx] = x
                mean, std = gp.predict(X, return_std=True)

                color = plt.cm.tab10(k)
                ax.plot(x, mean, lw=.2, color=color, zorder=30)
                ax.fill_between(
                    x, mean - std, mean + std,
                    lw=0, color=color, alpha=.3, zorder=20
                )

            ax.set_xlim(xlim)
            ax.set_ylim(ylim)

            ax.set_xlabel(label)
            ax.set_ylabel('PC {}'.format(ny))


if __name__ == '__main__':
    import argparse
    from matplotlib.mathtext import MathTextWarning

    warnings.filterwarnings(
        'ignore',
        category=MathTextWarning,
        message='Substituting with a symbol from Computer Modern.'
    )

    choices = list(plot_functions)

    def arg_to_plot(arg):
        arg = Path(arg).stem
        if arg not in choices:
            raise argparse.ArgumentTypeError(arg)
        return arg

    parser = argparse.ArgumentParser(description='generate plots')
    parser.add_argument(
        'plots', nargs='*', type=arg_to_plot, metavar='PLOT',
        help='{} (default: all)'.format(', '.join(choices).join('{}'))
    )
    args = parser.parse_args()

    if args.plots:
        for p in args.plots:
            plot_functions[p]()
    else:
        for f in plot_functions.values():
            f()
