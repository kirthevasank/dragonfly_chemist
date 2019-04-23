"""
CartesianProductGP implementation working on molecular domains.
Kernels are in mols/mol_kernels.py
@author: kkorovin@cs.cmu.edu

TODO:
* check values in get_molecular_kernel
"""

# general imports
import numpy as np

# imports from dragonfly
from dragonfly.exd import domains
from dragonfly.gp.kernel import CartesianProductKernel,  SEKernel
from dragonfly.utils.option_handler import get_option_specs, load_options
from dragonfly.utils.reporters import get_reporter
# local imports
from mols.mol_kernels import mol_kern_factory, MOL_GRAPH_INT_KERNEL_TYPES, MOL_GRAPH_CONT_KERNEL_TYPES, \
                   MOL_FINGERPRINT_KERNEL_TYPES, MOL_SIMILARITY_KERNEL_TYPES, MOL_DISTANCE_KERNEL_TYPES


# classes and functions to redefine
from dragonfly.gp.cartesian_product_gp import cartesian_product_gp_args,\
    cartesian_product_mf_gp_args,\
    _prep_kernel_hyperparams_for_euc_int_kernels,\
    _prep_kernel_hyperparams_for_discrete_kernels,\
    _prep_kernel_hyperparams_for_nn_kernels,\
    get_euclidean_integral_gp_kernel_with_scale,\
    get_discrete_kernel,\
    get_neural_network_kernel,\
    _get_euc_int_options
import dragonfly.gp.cartesian_product_gp as cartesian_product_gp

# TODO: append to this list the mol-dependent args
cartesian_product_gp_args += [get_option_specs('dom_mol_kernel_type', False, 'default',
                                               'Kernel type for Mol Domains.'),]

# Default kernel type for molecule domain
_DFLT_DOMAIN_MOL_KERNEL_TYPE = "edgehist_kernel"

###############################################################################
 # Setup helpers new definitions

def get_default_kernel_type(domain_type):
    """ 
    :return: default kernel type for the domain. 
    """
    if domain_type == 'molecule':
        return _DFLT_DOMAIN_MOL_KERNEL_TYPE
    else:
        raise ValueError('domain_type %s not yet supported'%(domain_type))

def _get_kernel_type_from_options(dom_type, dom_prefix, options):
    """
    :return: kernel type from options. 
    """
    dom_type_descr_dict = {'euclidean': 'euc',
                         'discrete_euclidean': 'euc',
                         'integral': 'int',
                         'prod_discrete_numeric': 'disc_num',
                         'prod_discrete': 'disc',
                         'neural_network': 'nn',
                         'molecule': 'mol'
                        }
    if dom_type not in dom_type_descr_dict.keys():
        raise ValueError('Unknown domain type %s.'%(dom_type))
    attr_name = '%s_%s_kernel_type'%(dom_prefix, dom_type_descr_dict[dom_type])
    return getattr(options, attr_name)

def _set_up_hyperparams_for_domain(fitter, X_data, gp_domain, dom_prefix,
                                   kernel_ordering, kernel_params_for_each_domain,
                                   dist_computers, lists_of_dists):
    """ 
    Called in `MolCPGPFitter._child_set_up`
    :side:  Add hyperparameter to `fitter.param_order`
            Add values/bounds to `fitter.dscr_hp_vals` or `fitter.cts_hp_bounds`
    """
    for dom_idx, dom, kernel_type in zip(range(gp_domain.num_domains), gp_domain.list_of_domains, kernel_ordering):
        dom_type = dom.get_type()
        dom_identifier = '%s-%d-%s'%(dom_prefix, dom_idx, dom_type)
        # Kernel type
        if kernel_type == '' or kernel_type is None:
            # If none is specified, use the one given in options
            kernel_type = _get_kernel_type_from_options(dom_type, dom_prefix,
                                                        fitter.options)
        if kernel_type == 'default':
            # Get default kernel for each domain
            kernel_type = get_default_kernel_type(dom.get_type())

        # Some conditional options
        if dom_type == 'molecule':
            print(f"_set_up_hyperparams_for_domain: Selected kernel_type: {kernel_type}")
            if kernel_type in MOL_GRAPH_CONT_KERNEL_TYPES:
                fitter.cts_hp_bounds.append([0, 5])
                fitter.param_order.append(["par", "cts"])
            elif kernel_type in MOL_GRAPH_INT_KERNEL_TYPES:
                fitter.dscr_hp_vals.append([1, 2, 3])
                fitter.param_order.append(["par", "dscr"])
            elif kernel_type in MOL_DISTANCE_KERNEL_TYPES:
                # print('passed in _set_up_hyperparams_for_domain')
                raise NotImplementedError("Not implemented setting up hyperparameters for {}".format(kernel_type))
            elif kernel_type in MOL_FINGERPRINT_KERNEL_TYPES:
                raise NotImplementedError("Not implemented setting up hyperparameters for {}".format(kernel_type))
            elif kernel_type in MOL_SIMILARITY_KERNEL_TYPES:
                raise NotImplementedError("Not implemented setting up hyperparameters for {}".format(kernel_type))
            else:
                raise ValueError('Unknown kernel type "%s" for "%s" spaces.'%(kernel_type, dom_type))
        else:
            raise ValueError('Unknown kernel type "%s" for "%s" spaces.'%(kernel_type, dom_type))

def _prep_kernel_hyperparams_for_molecular_domain(kernel_type, dom, kernel_params_for_dom):
    """ 
    Called in `_build_kernel_for_domain`
    Prepares the kernel hyper-parameters necessary for molecule domain
    """
    hyperparameters = vars(kernel_params_for_dom)
    hyperparameters['mol_type'] = dom.mol_type
    hyperparameters['kernel_type'] = kernel_type
    return hyperparameters

def get_molecular_kernel(kernel_hyperparams,
                         gp_cts_hps, gp_dscr_hps):
    """ 
    Called in `_build_kernel_for_domain`
    kernel_hyperparams: dictionary
    gp_cts_hps, gp_dscr_hps - this may be modified and returned
    """
    # pop the optimized int_par/cont_par from the `gp_dscr_hps`/`gp_cts_hps`
    kernel_type = kernel_hyperparams["kernel_type"]
    if kernel_type in MOL_GRAPH_INT_KERNEL_TYPES:
        kernel_hyperparams["par"] = int(gp_dscr_hps[0])
        gp_dscr_hps = gp_dscr_hps[1:]
    elif kernel_type in MOL_GRAPH_CONT_KERNEL_TYPES:
        kernel_hyperparams["par"] = gp_cts_hps[0]
        gp_cts_hps = gp_cts_hps[1:]
    # TODO: implement for distance kernel_types
    elif kernel_type in MOL_DISTANCE_KERNEL_TYPES:
        raise NotImplementedError("Distance kernel hyperparameter setter is not implemented.")
        # smth like: kernel_hyperparams["base_kernel"] = SEKernel(dim=10)
    elif kernel_type in MOL_SIMILARITY_KERNEL_TYPES:
        raise NotImplementedError
    elif kernel_type in MOL_FINGERPRINT_KERNEL_TYPES:
        raise NotImplementedError
    else:
        raise ValueError("Unrecognized kernel type: {} for molecule domain".format(kernel_type))
    kern = mol_kern_factory(**kernel_hyperparams)
    return kern, gp_cts_hps, gp_dscr_hps

def _build_kernel_for_domain(domain, dom_prefix, kernel_scale, gp_cts_hps, gp_dscr_hps,
                            other_gp_params, options, kernel_ordering, kernel_params_for_each_domain):
    """ 
    Called in `MolCPGPFitter._child_build_gp` 
    Build kernel from continuous/discrete hyperparameter for each domain
    """
    kernel_list = []
    # Iterate through each domain and build the corresponding kernel
    for dom_idx, dom, kernel_type in zip(range(domain.num_domains), 
                                        domain.list_of_domains,
                                        kernel_ordering):
        dom_type = dom.get_type().lower()
        if kernel_type == '' or kernel_type is None:
            # If none is specified, use the one given in options
            kernel_type = _get_kernel_type_from_options(dom_type, 'dom', options)
        if kernel_type == 'default':
            kernel_type = get_default_kernel_type(dom.get_type())
        if dom_type in ['euclidean', 'integral', 'prod_discrete_numeric',
                        'discrete_euclidean']:
            curr_kernel_hyperparams = _prep_kernel_hyperparams_for_euc_int_kernels(
                                      kernel_type, dom, dom_prefix, options)
            use_same_bw, _, esp_kernel_type, _ = _get_euc_int_options(dom_type, 'dom', options)
            if hasattr(other_gp_params, 'add_gp_groupings') and \
                other_gp_params.add_gp_groupings is not None:
                add_gp_groupings = other_gp_params.add_gp_groupings[dom_idx]
            else:
                add_gp_groupings = None
            curr_kernel, gp_cts_hps, gp_dscr_hps = \
                get_euclidean_integral_gp_kernel_with_scale(kernel_type, 1.0, \
                curr_kernel_hyperparams, gp_cts_hps, gp_dscr_hps, use_same_bw,
                add_gp_groupings, esp_kernel_type)
        elif dom_type == 'prod_discrete':
            curr_kernel_hyperparams = _prep_kernel_hyperparams_for_discrete_kernels(
                                         kernel_type, dom, dom_prefix, options)
            curr_kernel, gp_cts_hps, gp_dscr_hps = \
                get_discrete_kernel(kernel_type, curr_kernel_hyperparams, gp_cts_hps,
                                    gp_dscr_hps)
        elif dom_type == 'neural_network':
            curr_kernel_hyperparams = _prep_kernel_hyperparams_for_nn_kernels(
                                      kernel_type, dom,
                                      kernel_params_for_each_domain[dom_idx])
            curr_kernel, gp_cts_hps, gp_dscr_hps = \
                get_neural_network_kernel(kernel_type, curr_kernel_hyperparams, gp_cts_hps,
                                      gp_dscr_hps)
        elif dom_type == 'molecule':
            curr_kernel_hyperparams = _prep_kernel_hyperparams_for_molecular_domain(
                                      kernel_type, dom,
                                      kernel_params_for_each_domain[dom_idx],)
            curr_kernel, gp_cts_hps, gp_dscr_hps = \
                get_molecular_kernel(curr_kernel_hyperparams, gp_cts_hps, gp_dscr_hps)
        else:
          raise NotImplementedError(('Not implemented _child_build_gp for dom_type ' +
                                     '%s yet.')%(dom_type))
        kernel_list.append(curr_kernel)
    return CartesianProductKernel(kernel_scale, kernel_list), gp_cts_hps, gp_dscr_hps

# API classes ------------------------------------------------------------------------------------

class MolCPGP(cartesian_product_gp.CPGP):
    """ this may not need any modifications at all:
        doesn't use any of the module's functions
    """
    pass


class MolCPGPFitter(cartesian_product_gp.CPGPFitter):
    def _child_set_up(self):
        """
        set up parameters for the MolCPGPFitter
        """
        self.param_order.append(["kernel_scale", "cts"])
        self.kernel_scale_log_bounds = [np.log(0.03 * self.Y_var), np.log(30 * self.Y_var)]
        self.cts_hp_bounds.append(self.kernel_scale_log_bounds)
        _set_up_hyperparams_for_domain(self, self.X, self.domain, "dom",
            self.domain_kernel_ordering,
            self.domain_kernel_params_for_each_domain,
            self.domain_dist_computers,
            self.domain_lists_of_dists)

    def _child_build_gp(self, mean_func, noise_var, gp_cts_hps, gp_dscr_hps,
                        other_gp_params=None, *args, **kwargs):
        log_kernel_scale = gp_cts_hps[0]
        gp_cts_hps = gp_cts_hps[1:]
        kernel_scale = np.exp(log_kernel_scale)
        mol_kernel, gp_cts_hps, gp_dscr_hps = _build_kernel_for_domain(
            self.domain, 'dom',
            kernel_scale, gp_cts_hps, gp_dscr_hps, other_gp_params, self.options,
            self.domain_kernel_ordering, self.domain_kernel_params_for_each_domain
        )
        ret_gp = MolCPGP(
            self.X, self.Y, mol_kernel, mean_func, noise_var,
            domain_lists_of_dists=self.domain_lists_of_dists, *args, **kwargs
        )
        return ret_gp, gp_cts_hps, gp_dscr_hps

