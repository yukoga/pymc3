from functools import partial

import numpy as np
import theano
import theano.tensor as T
from scipy import stats

from .dist_math import bound, factln, binomln, betaln, logpow
from .distribution import Discrete, draw_values, generate_samples

__all__ = ['Binomial',  'BetaBinomial',  'Bernoulli',  'Poisson',
           'NegativeBinomial', 'ConstantDist', 'ZeroInflatedPoisson',
           'DiscreteUniform', 'Geometric', 'Categorical']


class Binomial(Discrete):
    R"""
    Binomial log-likelihood.

    The discrete probability distribution of the number of successes
    in a sequence of n independent yes/no experiments, each of which
    yields success with probability p.

    .. math:: f(x \mid n, p) = \binom{n}{x} p^x (1-p)^{n-x}

    ========  ==========================================
    Support   :math:`x \in \{0, 1, \ldots, n\}`
    Mean      :math:`n p`
    Variance  :math:`n p (1 - p)`
    ========  ==========================================

    Parameters
    ----------
    n : int
        Number of Bernoulli trials (n >= 0).
    p : float
        Probability of success in each trial (0 < p < 1).
    """
    def __init__(self, n, p, *args, **kwargs):
        super(Binomial, self).__init__(*args, **kwargs)
        self.n = n
        self.p = p
        self.mode = T.cast(T.round(n * p), self.dtype)

    def random(self, point=None, size=None, repeat=None):
        n, p = draw_values([self.n, self.p], point=point)
        return generate_samples(stats.binom.rvs, n=n, p=p,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        n = self.n
        p = self.p

        return bound(
            binomln(n, value) + logpow(p, value) + logpow(1 - p, n - value),
            0 <= value, value <= n,
            0 <= p, p <= 1)


class BetaBinomial(Discrete):
    R"""
    Beta-binomial log-likelihood.

    Equivalent to binomial random variable with success probability
    drawn from a beta distribution.

    .. math::

       f(x \mid \alpha, \beta, n) =
           \binom{n}{x}
           \frac{B(x + \alpha, n - x + \beta)}{B(\alpha, \beta)}

    ========  =================================================================
    Support   :math:`x \in \{0, 1, \ldots, n\}`
    Mean      :math:`n \dfrac{\alpha}{\alpha + \beta}`
    Variance  :math:`n \dfrac{\alpha \beta}{(\alpha+\beta)^2 (\alpha+\beta+1)}`
    ========  =================================================================

    Parameters
    ----------
    n : int
        Number of Bernoulli trials (n >= 0).
    alpha : float
        alpha > 0.
    beta : float
        beta > 0.
    """
    def __init__(self, alpha, beta, n, *args, **kwargs):
        super(BetaBinomial, self).__init__(*args, **kwargs)
        self.alpha = alpha
        self.beta = beta
        self.n = n
        self.mode = T.cast(T.round(alpha / (alpha + beta)), 'int8')

    def _random(self, alpha, beta, n, size=None):
        size = size or 1
        p = np.atleast_1d(stats.beta.rvs(a=alpha, b=beta, size=np.prod(size)))
        # Sometimes scipy.beta returns nan. Ugh.
        while np.any(np.isnan(p)):
            i = np.isnan(p)
            p[i] = stats.beta.rvs(a=alpha, b=beta, size=np.sum(i))
        # Sigh...
        _n, _p, _size = np.atleast_1d(n).flatten(), p.flatten(), np.prod(size)
        samples = np.reshape(stats.binom.rvs(n=_n, p=_p, size=_size), size)
        return samples

    def random(self, point=None, size=None, repeat=None):
        alpha, beta, n = \
            draw_values([self.alpha, self.beta, self.n], point=point)
        return generate_samples(self._random, alpha=alpha, beta=beta, n=n,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        alpha = self.alpha
        beta = self.beta
        return bound(binomln(self.n, value)
                     + betaln(value + alpha, self.n - value + beta)
                     - betaln(alpha, beta),
                     value >= 0, value <= self.n,
                     alpha > 0, beta > 0)


class Bernoulli(Discrete):
    R"""Bernoulli log-likelihood

    The Bernoulli distribution describes the probability of successes
    (x=1) and failures (x=0).

    .. math:: f(x \mid p) = p^{x} (1-p)^{1-x}

    ========  ======================
    Support   :math:`x \in \{0, 1\}`
    Mean      :math:`p`
    Variance  :math:`p (1 - p)`
    ========  ======================

    Parameters
    ----------
    p : float
        Probability of success (0 < p < 1).
    """
    def __init__(self, p, *args, **kwargs):
        super(Bernoulli, self).__init__(*args, **kwargs)
        self.p = p
        self.mode = T.cast(T.round(p), 'int8')

    def random(self, point=None, size=None, repeat=None):
        p = draw_values([self.p], point=point)
        return generate_samples(stats.bernoulli.rvs, p,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        p = self.p
        return bound(
            T.switch(value, T.log(p), T.log(1 - p)),
            value >= 0, value <= 1,
            p >= 0, p <= 1)


class Poisson(Discrete):
    R"""
    Poisson log-likelihood.

    Often used to model the number of events occurring in a fixed period
    of time when the times at which events occur are independent.

    .. math:: f(x \mid \mu) = \frac{e^{-\mu}\mu^x}{x!}

    ========  ==========================
    Support   :math:`x \in \mathbb{N}_0`
    Mean      :math:`\mu`
    Variance  :math:`\mu`
    ========  ==========================

    Parameters
    ----------
    mu : float
        Expected number of occurrences during the given interval
        (mu >= 0).

    Notes
    -----
    The Poisson distribution can be derived as a limiting case of the
    binomial distribution.
    """
    def __init__(self, mu, *args, **kwargs):
        super(Poisson, self).__init__(*args, **kwargs)
        self.mu = mu
        self.mode = T.floor(mu).astype('int32')

    def random(self, point=None, size=None, repeat=None):
        mu = draw_values([self.mu], point=point)
        return generate_samples(stats.poisson.rvs, mu,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        mu = self.mu
        return bound(
            logpow(mu, value) - factln(value) - mu,
            mu >= 0, value >= 0)


class NegativeBinomial(Discrete):
    R"""
    Negative binomial log-likelihood.

    The negative binomial distribution describes a Poisson random variable
    whose rate parameter is gamma distributed.

    .. math::

       f(x \mid \mu, \alpha) =
           \frac{\Gamma(x+\alpha)}{x! \Gamma(\alpha)}
           (\alpha/(\mu+\alpha))^\alpha (\mu/(\mu+\alpha))^x

    ========  ==========================
    Support   :math:`x \in \mathbb{N}_0`
    Mean      :math:`\mu`
    ========  ==========================

    Parameters
    ----------
    mu : float
        Poission distribution parameter (mu > 0).
    alpha : float
        Gamma distribution parameter (alpha > 0).
    """
    def __init__(self, mu, alpha, *args, **kwargs):
        super(NegativeBinomial, self).__init__(*args, **kwargs)
        self.mu = mu
        self.alpha = alpha
        self.mode = T.floor(mu).astype('int32')

    def random(self, point=None, size=None, repeat=None):
        mu, alpha = draw_values([self.mu, self.alpha], point=point)
        g = generate_samples(stats.gamma.rvs, alpha, scale=alpha / mu,
                             dist_shape=self.shape,
                             size=size)
        g[g == 0] = np.finfo(float).eps  # Just in case
        return stats.poisson.rvs(g)

    def logp(self, value):
        mu = self.mu
        alpha = self.alpha
        negbinom = bound(binomln(value + alpha - 1, value)
                         + logpow(mu / (mu + alpha), value)
                         + logpow(alpha / (mu + alpha), alpha),
                         value >= 0, mu > 0, alpha > 0)

        # Return Poisson when alpha gets very large.
        return T.switch(1 * (alpha > 1e10),
                        Poisson.dist(self.mu).logp(value),
                        negbinom)


class Geometric(Discrete):
    R"""
    Geometric log-likelihood.

    The probability that the first success in a sequence of Bernoulli
    trials occurs on the x'th trial.

    .. math:: f(x \mid p) = p(1-p)^{x-1}

    ========  =============================
    Support   :math:`x \in \mathbb{N}_{>0}`
    Mean      :math:`\dfrac{1}{p}`
    Variance  :math:`\dfrac{1 - p}{p^2}`
    ========  =============================

    Parameters
    ----------
    p : float
        Probability of success on an individual trial (0 < p <= 1).
    """
    def __init__(self, p, *args, **kwargs):
        super(Geometric, self).__init__(*args, **kwargs)
        self.p = p
        self.mode = 1

    def random(self, point=None, size=None, repeat=None):
        p = draw_values([self.p], point=point)
        return generate_samples(np.random.geometric, p,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        p = self.p
        return bound(T.log(p) + logpow(1 - p, value - 1),
                     0 <= p, p <= 1, value >= 1)


class DiscreteUniform(Discrete):
    R"""
    Discrete uniform distribution.

    .. math:: f(x \mid lower, upper) = \frac{1}{upper-lower}

    ========  ===============================================
    Support   :math:`x \in {lower, lower + 1, \ldots, upper}`
    Mean      :math:`\dfrac{lower + upper}{2}`
    Variance  :math:`\dfrac{(upper - lower)^2}{12}`
    ========  ===============================================

    Parameters
    ----------
    lower : int
        Lower limit.
    upper : int
        Upper limit (upper > lower).
    """
    def __init__(self, lower, upper, *args, **kwargs):
        super(DiscreteUniform, self).__init__(*args, **kwargs)
        self.lower = T.floor(lower).astype('int32')
        self.upper = T.floor(upper).astype('int32')
        self.mode = T.floor((upper - lower) / 2.).astype('int32')

    def _random(self, lower, upper, size=None):
        # This way seems to be the only to deal with lower and upper
        # as array-like.
        samples = stats.uniform.rvs(lower, upper - lower - np.finfo(float).eps,
                                    size=size)
        return np.floor(samples).astype('int32')

    def random(self, point=None, size=None, repeat=None):
        lower, upper = draw_values([self.lower, self.upper], point=point)
        return generate_samples(self._random,
                                lower, upper,
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        upper = self.upper
        lower = self.lower
        return bound(-T.log(upper - lower + 1),
                     lower <= value, value <= upper)


class Categorical(Discrete):
    R"""
    Categorical log-likelihood.

    The most general discrete distribution.

    .. math:: f(x \mid p) = p_x

    ========  ===================================
    Support   :math:`x \in \{1, 2, \ldots, |p|\}`
    ========  ===================================

    Parameters
    ----------
    p : float
        p > 0 and the elements of p must sum to 1.
    """
    def __init__(self, p, *args, **kwargs):
        super(Categorical, self).__init__(*args, **kwargs)
        try:
            self.k = np.shape(p)[-1].tag.test_value
        except AttributeError:
            self.k = np.shape(p)[-1]
        self.p = T.as_tensor_variable(p)
        self.mode = T.argmax(p)


    def random(self, point=None, size=None, repeat=None):
        p, k = draw_values([self.p, self.k], point=point)
        return generate_samples(partial(np.random.choice, np.arange(k)),
                                p=p,
                                broadcast_shape=p.shape[:-1] or (1,),
                                dist_shape=self.shape,
                                size=size)

    def logp(self, value):
        p = self.p
        k = self.k

        sumto1 = theano.gradient.zero_grad(T.le(abs(T.sum(p, axis=-1) - 1), 1e-5))
        if p.ndim > 1:
            a = T.log(p[T.arange(p.shape[0]), value])
        else:
            a = T.log(p[value])
        return bound(a,
                     value >= 0, value <= (k - 1),
                     sumto1)


class ConstantDist(Discrete):
    """
    Constant log-likelihood.

    Parameters
    ----------
    value : float or int
        Constant parameter.
    """
    def __init__(self, c, *args, **kwargs):
        super(ConstantDist, self).__init__(*args, **kwargs)
        self.mean = self.median = self.mode = self.c = c

    def random(self, point=None, size=None, repeat=None):
        c = draw_values([self.c], point=point)
        dtype = np.array(c).dtype

        def _random(c, dtype=dtype, size=None):
            return np.full(size, fill_value=c, dtype=dtype)

        return generate_samples(_random, c=c, dist_shape=self.shape,
                                size=size).astype(dtype)

    def logp(self, value):
        c = self.c
        return bound(0, T.eq(value, c))


class ZeroInflatedPoisson(Discrete):
    def __init__(self, theta, z, *args, **kwargs):
        super(ZeroInflatedPoisson, self).__init__(*args, **kwargs)
        self.theta = theta
        self.z = z
        self.pois = Poisson.dist(theta)
        self.const = ConstantDist.dist(0)
        self.mode = self.pois.mode

    def random(self, point=None, size=None, repeat=None):
        theta = draw_values([self.theta], point=point)
        # To do: Finish me
        return None

    def logp(self, value):
        return T.switch(self.z,
                        self.pois.logp(value),
                        self.const.logp(value))
