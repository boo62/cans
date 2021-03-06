"""Parameter guessing classes and functions.

Not yet able to provide plate_lvl parameters, e.g. from a genetic
algortihm candidate, for logistic equvalent guessing (instead
inferred). I haven't needed to yet because I have been using the
imaginary neighbour model instead.

"""

import numpy as np


from cans.model import IndeModel, ImagNeighModel
from cans.plate import Plate


def fit_log_eq(plate, plate_model, b_guess,
               area_ratio=1.0, C_ratio=1e-5,
               kn_start=0, kn_stop=2.0, kn_num=21):
    """Simulate a Plate and carry out a quick fit.

    Return a Plate containing the estimates in Cultures.

    plate_model : CANS Model instance to simulate values for the plate.

    true_params : np.array of all parameters required for comp_model
    ordered according to comp_model.params and with culture level
    parameters supplied for all cultures.

    b_guess : Guess for parameter b. One guess for all cultures. The
    quick fit aims to improve upon this.

    kn_start, kn_stop, and kn_num define values (using np.linspace) of
    kn for which the plate_model is simulated using last stage guesses
    of other parameters. For a given set of other parameters there is
    a linear relationship between final cell measurement variance and
    kn.

    See Guesser documentation for area_ratio and C_ratio.

    """
    guesser = Guesser(plate, plate_model,
                      area_ratio=area_ratio, C_ratio=C_ratio)
    quick_guess = guesser.quick_fit_log_eq(b_guess)
    quick_guess = guesser.guess_kn(kn_start, kn_stop, kn_num, quick_guess)
    return quick_guess, guesser


def fit_imag_neigh(plate, plate_model, area_ratio, C_ratio,
                   imag_neigh_params, no_neighs=None, kn_start=0.0,
                   kn_stop=2.0, kn_num=21, plate_lvl=None):
    """Simulate a Plate and carry out a quick fit.

    Return a tuple of a parameter guess and the Guesser object used to
    make the guess.

    plate_model : CANS Model instance to simulate values for the plate.

    See Guesser.quick_fit_log_eq documentation for information on
    C_doubt and N_doubt and how the

    imag_neigh_params : List or np.array of parameter guesses/settings
    for the imaginary neigbour model excluding initial amounts
    (['kn1', 'kn2', 'b-', 'b+', 'b']). kn1 and kn2 are guesses; b- and
    b+ are fixed growth constants (settings) for the slow and fast
    growing neighbours; b is a guess for the parameter of interest
    used for all cultures. (It is recomended to set 'b+'=1.5*'b'.)

    no_neighs : The number of each type of imaginary neighbour to
    include in the model. If None, a number will be calculated
    such that the final amount of cells in the highest growing
    cultures is less than the total amount of nutrients available
    from the culture and the slow growing neighbours.

    plate_lvl : Plate level parameters to use, rather than inferring
    from the data. If provided then these are returned with the b
    estimates (rather than inferred values) and the user need not
    provide kn_* arguments as they will not be used. The user can
    provide a C_ratio of None if plate level parameters are provided.

    kn_start, kn_stop, and kn_num define values (using np.linspace) of
    kn for which the plate_model is simulated using last stage guesses
    of other parameters. For a given set of other parameters there is
    a linear relationship between final cell measurement variance and
    kn.

    See Guesser documentation for area_ratio and C_ratio.

    """
    guesser = Guesser(plate, plate_model,
                      area_ratio=area_ratio, C_ratio=C_ratio)
    kwargs = {
        "imag_neigh_params": imag_neigh_params,
        "no_neighs": no_neighs,
        "plate_lvl": plate_lvl,
    }
    quick_guess = guesser.quick_fit_imag_neighs(**kwargs)
    if plate_lvl is None:
        quick_guess = guesser.guess_kn(kn_start, kn_stop, kn_num, quick_guess)
    return quick_guess, guesser


class Guesser(object):
    def __init__(self, plate, model, area_ratio=1.0, C_ratio=1e-4):
        """Instantiate Guesser with a Plate and Model.

        plate : CANS Plate object.

        model : CANS Model object. The plate model for the final fit
        (e.g. CompModel() or CompModelBC()) rather than the gussesing
        model.

        area_ratio : Ratio of (edge culture area / internal culture
        area). This is not the area of the cultures, which are assumed
        equal, but the area of agar that is closest to, and could be
        said to belong to, a culture. (Assumed equal to Ne/Ni.) Used
        if model is CompModelBC but ignored if model is CompModel. Can
        set to None if supplying plate level parameters. In such a
        case the value is not accessed anyway.

        C_ratio : (Init cell amounts / final cell amounts). The user
        must provide a guess for the ratio based on knowledge about
        the experiment. The data does not have resolution enough to
        determine starting cell amounts and, unlike for nutrient
        amounts, there is no easy way to infer a guess without
        fitting. If C_0 is not to be inferred from the data, e.g. if
        using a genetic algorithm candidate of plate level parameters
        with imaginary neighbour guessing, then the user can supply
        the value None. It shouldn't matter becuase in this case the
        value should not be accessed anyway.

        """
        self.plate = plate
        self.model = model
        if area_ratio is None:
            self.area_ratio = None
        else:
            self.area_ratio = float(area_ratio)
        if C_ratio is None:
            self.C_ratio = None
        else:
            self.C_ratio = float(C_ratio)


    def _guess_init_N(self):
        """Guess starting amounts of Nutrients.

        If the model treats all cultures as having the same starting
        amount of nutrients (i.e. if model.species_bc contains an
        empty string at the index of species "N"), returns a single.
        element list [N_all]. If the model contains separate
        parameters for initial nutrients in internal and edge
        cultures, returns a two element list of initial nutrient
        amounts [Ni, Ne].

        """
        # Assuming complete reactions and relatively small starting
        # amounts of cells, total nutrient amount is equal to the
        # total final cell amount. Do not include empty cultures in
        # the sum.
        N_tot = np.sum(self.plate.c_meas_obj[-len(self.plate.growers):])
        N_index = self.model.species.index("N")
        if self.model.species_bc[N_index]:
            # Number of internal and edge cultures.
            ni = len(self.plate.internals)
            ne = len(self.plate.edges)
            # Init nutrients in internal and edge cultures. Derived
            # from the following relationships: N_tot = ni*Ni + ne*Ne;
            # Ne = Ni*ratio.
            Ni = N_tot / (ni + ne*self.area_ratio)
            Ne = (N_tot - ni*Ni) / ne
            return [Ni, Ne]
        else:
            N_all = N_tot / float(self.plate.no_cultures)
            return [N_all]


    # Could write additional code to remove very slow or non-growing
    # cultures from the average. For plate 15, however, most cells
    # exhibit some growth. We hope to get a better guess from fits of
    # the logistic equivalent of imaginary neighbour model anyway so
    # don't worry too much.
    def _guess_init_C(self):
        """Guess initial cell amounts.

        Returns a single element list containing an intial guess of
        cell amounts applicable to all cultures on the plate.

        C_0 guess may be revised after fitting the logistic equivalent
        or imaginary neighbour model but those methods also require a
        guess.

        """
        # Just take ratio of maximum of final cells without special
        # treatment of edge and internal cultures because, for typical
        # dilution methods, the ratio is likely to be a fairly rough
        # guess anyway. We will revise the guess anyway after fitting
        # the logistic equivalent of imaginary neighbour
        # model. Previously
        # (https://boo62.github.io/blog/fits-of-overlapping-5x5-zones/),
        # I carried out many fits using a grid of initial guesses and
        # these were not very dependent on the accuracy of the initial
        # guess of C_0.
        # Take the maximum times the C_ratio.
        C_0 = max(self.plate.c_meas[-self.plate.no_cultures:])*self.C_ratio
        return [C_0]


    def _bound_init_amounts(self, guess, C_doubt=1e3, N_doubt=2.0):
        """Return list of bounds for init amounts.

        guess : List of guesses of init amounts.

        C_doubt : Factor for Uncertainty in guess of initial cell
        amounts. Divides and multiplies the initial guess of C_0 to create
        lower and upper bounds.

        N_doubt : Factor for Uncertainty in guess of initial nutrient
        amounts. Divides and/or multiplies the initial guess(es) to
        create lower and upper bounds. See code for exact usage.

        """
        # Bound cells.
        bounds = [(guess[0]/C_doubt, guess[0]*C_doubt)]
        # Bound nutrients.
        N_index = self.model.species.index("N")
        if not self.model.species_bc[N_index]:
            # Bound N_0. This is strongly coupled to the final amount
            # of cells so, assuming relatively small intial cell
            # amounts, we can be fairly strict with a lower bound. The
            # upper bound depends on whether the reactions are
            # complete at the time of the final cell measurement.
            bounds.append((guess[1]*0.9, guess[1]*N_doubt))
        else:
            # Bound N_0 and NE_0. Cannot be as strict with N_0 in this
            # case as the minimum value is dependent on the accuracy
            # of the area_ratio and the level of diffusion between
            # edges and internals which is unknown. If we were sure of
            # the value of area_ratio and that all nutrients were used
            # up we could bound one limit of each amount using the
            # guess of the other amount. I choose not to be so strict.
            bounds.append((guess[1]/N_doubt, guess[1]*N_doubt))
            bounds.append((guess[2]/N_doubt, guess[2]*N_doubt))
        return bounds


    def get_bounds(self, params, C_doubt=1e3, N_doubt=2.0, kn_max=10.0):
        """Return bounds for estimated parameters."""
        amount_bounds = self._bound_init_amounts(params, C_doubt, N_doubt)
        kn_bound = [(0, kn_max)]
        b_bounds = [(0, None) for i in range(self.plate.no_cultures)]
        bounds = amount_bounds + kn_bound + b_bounds
        return np.array(bounds)


    def _sep_by_N_0(self, param_guess, bounds):
        """Separate parameter guesses and bounds by N_0 guess.

        This way guesses and bounds can be used to fit single
        cultures when making quick initial guesses.

        param_guess and bounds should be numpy arrays with N_0 indices
        starting at one.

        Returns lists of length one if there is one N_0 in the model
        and lists of length two if there is is also an N_0 for edge
        cultures.

        """
        N_index = self.model.species.index("N")
        if self.model.species_bc[N_index]:
            param_guess = np.array([np.delete(param_guess, 2), np.delete(param_guess, 1)])
            bounds = np.array([np.delete(bounds, 2, 0), np.delete(bounds, 1, 0)])
        else:
            param_guess = np.array([param_guess])
            bounds = np.array([bounds])
        return param_guess, bounds


    def _get_top_half_C_f_ests(self, all_ests):
        """Return np.array of estimates for Cultures with highest final Cells.

        If the number of cultures is odd return the larger portion.

        all_ests : estimates for all cultures.

        """
        # Measured final cell amounts.
        C_fs = self.plate.c_meas[-self.plate.no_cultures:]
        C_f_sorted = [est for (C_f, est) in sorted(zip(C_fs, all_ests))]
        # Indices of cultures sorted by C_f. May use later.
        # labelled_C_fs = [tup for tup in enumerate(C_fs)]
        # ordered_C_fs = sorted(labelled_C_fs, key=lambda tup: tup[1])
        # C_f_sorted_indices = [i for i, C in ordered_C_fs]
        top_half_ests = C_f_sorted[self.plate.no_cultures//2:]
        return np.array(top_half_ests)


    def _process_quick_ests(self, quick_mod, est_name, b_guess, clip=False,
                            C_0_handling="first_guess", plate_lvl=None):
        """Process estimates from quick fits.

        Take a mean of estimated C_0s, use the N_0 guess(es) made from
        average final cell amounts, and add on b guesses from the
        quick fit.

        quick_mod : Instance of the model used for quick fit.

        est_name : Name of the Culture attribute where estimated
        values are stored. Either "log_est" or "im_neigh_est".

        C_0_handling : Specify method for processing C_0 estimates:
        "first_guess" to not use the results of fits; "median" for median of
        all cultures; "top_half" for the median of only the cultures with
        highest final cells. This is because cultures with zero growth can be
        fit with arbitrary initial amounts.

        clip : If True, clip b_ests at 3x b_guess to avoid extreme values.

        b_guess : Original user provided b_guess.

        plate_lvl : Optional plate level parameters to use instead of inferring.

        """


        # Allow to raise AttributeError if bad est_name.
        all_ests = np.array([getattr(c, est_name).x for i, c in enumerate(self.plate.cultures)
                             if i in self.plate.growers])
        b_ests = all_ests[:, quick_mod.b_index]
        if clip:
            b_ests.clip(max=3.0*b_guess, out=b_ests)    # "out" for inplace clipping.

        # Insert b_ests leaving empties as zero
        b_est_holder = np.zeros(self.plate.no_cultures)
        b_est_holder[self.plate.growers] = b_ests
        b_ests = b_est_holder

        if plate_lvl is not None:
            # Don't bother to infer plate level parameters and return
            # early.
            return np.concatenate((plate_lvl, b_ests))

        if C_0_handling == "first_guess":
            C_0_guess = self._guess_init_C()
        elif C_0_handling == "median":
            C_0_guess = [np.median(all_ests[:, 0])]
        elif C_0_handling == "top_half":
            # Select estimates to use for taking average of init
            # C_0. Cultures with a zero b estimate have arbitrary init
            # amount ests. It is possible that more than half of
            # cultures have a zero b estimate, in which case we would
            # have to remove more than just the lowest half. If the
            # issue is due to the plate having gaps we could use
            # plate.empties to deal with this.
            included_ests = self._get_top_half_C_f_ests(all_ests)
            C_0_guess = [np.median(included_ests[:, 0])]

        # Use N_0 guess(es) made from average final cell amounts.
        N_0_guess = self._guess_init_N()
        # N_guess may be a single value. We need an iterable to
        # concatenate with guesses of other parameters.
        try:
            list(N_0_guess)
        except TypeError:
            N_0_guess = [N_0_guess]

        # N_guess may be a single value. We need an iterable to
        # concatenate with other guesses.
        new_guess = np.concatenate((C_0_guess, N_0_guess, b_ests))
        # Insert nan at index of kn.
        kn_index = self.model.params.index("kn")
        new_guess = np.insert(new_guess, kn_index, np.nan)
        return new_guess


    def make_first_guess(self, b_guess):
        """Make a first guess without any fitting.

        Returns guesses for the following parameters:

        C_0_guess : Determined from the Guesser attribute C_ratio; a user
        defined approximate ratio between initial and final cells.

        N_0_guess : Determined from average final cell measurements.

        b_guess : A single user defined guess used for all cultures.

        """
        C_0_guess = self._guess_init_C()
        N_0_guess = self._guess_init_N()    # May be length 2.
        amount_guess = np.append(C_0_guess, N_0_guess)
        first_guess = np.append(amount_guess, b_guess)
        return first_guess


    # It would be possible to find specific estimates for b, before
    # any fitting, by scaling an average guess by final cell
    # amounts. Alternatively we could guess a maximum and scale
    # towards zero. However, the factor by which to scale would depend
    # on kn and the absolute value of the average (and possibly also
    # initial cell amounts?). I hope to find reasonable geusses
    # without the need for this.
    def quick_fit_log_eq(self, b_guess):
        """Guess b by fitting the logistic equivalent model.

        Returns guesses for all parameters in self.model for a
        self.model of CompModel or CompModelBC.

        Fits to individual cultures. For speed, there is no collective
        fitting of plate level parameters, e.g. initial
        amounts. Instead, an average can be taken after the individual
        fits. Individual b parameters result from fitting. Guesses for
        N_0 are infered from average final measurements and not
        updated after fitting. C_0 is guessed using C_ratio (see
        make_first_guess) and then fixed for fitting.

        b_guess : guess for b parameter. The same for all cultures.

        This N_0_guess is not used in logistic equivalent fits but
        is returned in the new_guess; logistic estimated N_0s are not
        realistic for the competition model.

        """
        first_guess = self.make_first_guess(b_guess)
        C_0_guess = [first_guess[0]]
        # Use final amounts of cells as inital guesses of nutrients
        # because logistic equivalent growth is governed by N + C ->
        # 2C, there is no diffusion, and C_0 is assumed to be
        # relatively small.
        C_fs = self.plate.c_meas[-self.plate.no_cultures:]
        log_eq_N_0_guesses = C_fs
        log_eq_guesses = [C_0_guess + [N_0, b_guess] for N_0 in log_eq_N_0_guesses]
        # For logistic equivalent bound C_0 and allow N_0 and b to
        # vary freely. It would perhaps be better to fit C_0
        # collectively but this would be much slower. [C_0, N_0, b]
        log_eq_bounds = [(C_0_guess[0], C_0_guess[0]), (0.0, None), (0.0, None)]
        log_eq_mod = IndeModel()
        for guess, culture in zip(log_eq_guesses, self.plate.cultures):
            culture.log_est = culture.fit_model(log_eq_mod,
                                                param_guess=guess,
                                                bounds=log_eq_bounds)

        new_guess = self._process_quick_ests(log_eq_mod,
                                             est_name="log_est",
                                             C_0_handling="first_guess",
                                             b_guess=b_guess)
        return new_guess


    def quick_fit_imag_neighs(self, imag_neigh_params,
                              no_neighs=None, plate_lvl=None):
        """Guess b by fitting the imaginary neighbour model.

        b_guess : guess for b parameter. The same for all cultures.

        plate_lvl : Plate level parameters to use rather than
        inferring from data. Usually candidates of plate-level
        parameters from a genetic algorithm. If plate_lvl is provided
        then only then these are returned in from of the b_estimates.

        no_neighs : The number of each type of imaginary neighbour to
        include in the model. If None an number will be calculated
        such that the the total amount of nutrients available from the
        culture and the slow growing neighbours is greater than the
        final amount of cells in the highest growing culture.

        """
        N_index = self.model.species.index("N")
        N_bc = bool(self.model.species_bc[N_index])    # N boundary condition.
        b_guess = imag_neigh_params[-1]
        if plate_lvl is None:
            # Construct a first parameter guess of Guesser.model
            # parameters from final cell amounts and user supplied values.
            first_guess = self.make_first_guess(b_guess)
        elif list(plate_lvl) and N_bc:
            first_guess = np.concatenate((plate_lvl[:N_index+2], [b_guess]))
        elif list(plate_lvl) and not N_bc:
            first_guess = np.concatenate((plate_lvl[:N_index+1], [b_guess]))
        else:
            raise ValueError, "plate_lvl should evaluate True if provided."

        if no_neighs is None:
            if plate_lvl is None:
                N_0_min = min(self._guess_init_N())
            else:
                N_0_min = plate_lvl[N_index]
            C_f_max = max(self.plate.c_meas[-self.plate.no_cultures:])
            no_neighs = int(np.ceil(float(C_f_max)/N_0_min))

        imag_neigh_mod = ImagNeighModel(no_neighs)

        # Make bounds.
        amount_bounds = [(amount, amount) for amount in first_guess[:-1]]
        other_bounds = [
            (0.0, None), (0.0, None),
            (imag_neigh_params[2], imag_neigh_params[2]),
            (imag_neigh_params[3], imag_neigh_params[3]),
            (0.0,  None)
        ]
        neigh_bounds = np.concatenate((amount_bounds, other_bounds))

        # Add user supplied guesses of ['kn1', 'kn2', 'b-', 'b+', 'b']
        # to make neighbour model guesses and then separate guess and
        # bounds for internal and edge cultures if they have different
        # N_0s (compares inside _sep_by_N_0).
        imag_neigh_params = np.concatenate((first_guess[:-1],
                                            imag_neigh_params))
        imag_neigh_params, neigh_bounds = self._sep_by_N_0(imag_neigh_params,
                                                           neigh_bounds)

        for i, c in enumerate(self.plate.cultures):

            if not N_bc:
                N_0_index = 0
            elif N_bc and i in self.plate.internals:
                N_0_index = 0
            elif N_bc and i in self.plate.edges:
                N_0_index = 1

            # There is an inacuaracy here for N_0s of neighbours of
            # cultures at edges or next to an edge. For a full plate,
            # all edges but the corner cultures have two edge
            # neighbours and an internal neighbour. Internal cultures
            # next to an edge have one or two egde neighbours and two
            # or three internal neighbours. I do not bother to treat
            # the higher and lower initial nutrients (amounts but not
            # concentrations) of neighbours any differently in these
            # cultures. Instead the fit assumes edge cultures have
            # only edge neighbours, and internals have only internal
            # neighbours. You could supply a certain number of edge
            # and internal culture neighbours and adjust rate
            # equations appropriately but, for an initial guess, this
            # seems quite complicated. The effect diminishes as plate
            # size increases.
            if i in self.plate.empties:
                # b=0 is inserted in _process_quick_ests before
                # returning.
                continue
            else:
                c.im_neigh_est = c.fit_model(imag_neigh_mod,
                                             imag_neigh_params[N_0_index],
                                             neigh_bounds[N_0_index])
                                             # minimizer_opts={"disp": True})

        new_guess = self._process_quick_ests(imag_neigh_mod,
                                             est_name="im_neigh_est",
                                             b_guess=b_guess,
                                             clip=True,    # Cap b at 3*b_guess.
                                             C_0_handling="first_guess",
                                             plate_lvl=plate_lvl)
        return new_guess


    def guess_kn(self, start, stop, num, params):
        """Guess kn from final cell measurement variance.

        params should have a dummy value, e.g. nan, in place of
        kn. Returns this array with the guess of kn inserted.

        """
        C_f_var_true = np.var(self.plate.c_meas[-self.plate.no_cultures:])
        kns = np.linspace(start, stop, num)
        kn_index = self.model.params.index("kn")
        # Make a new Plate so that we do not alter the original
        # containing true data.
        sim_plate = Plate(self.plate.rows, self.plate.cols)
        sim_plate.times = self.plate.times
        C_f_vars = []
        for kn in kns:
            params[kn_index] = kn
            sim_plate.sim_params = params
            sim_plate.set_sim_data(self.model)
            C_fs = sim_plate.c_meas[-sim_plate.no_cultures:]
            C_f_vars.append(np.var(C_fs))
        # Fit a line by least squares.
        A = np.vstack([kns, np.ones(len(kns))]).T
        m, c = np.linalg.lstsq(A, C_f_vars)[0]
        kn_guess = (C_f_var_true - c)/float(m)
        params[kn_index] = kn_guess
        return params.clip(min=0.0)
