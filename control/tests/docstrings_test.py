# docstrings_test.py - test for undocumented arguments
# RMM, 28 Jul 2024
#
# This unit test looks through all functions in the package and attempts to
# identify arguments that are not documented.  It will check anything that
# is an explicitly listed argument, as well as attempt to find keyword
# arguments that are extracted using kwargs.pop(), config._get_param(), or
# config.use_legacy_defaults.

import inspect
import warnings

import pytest
import re
import numpydoc.docscrape as npd

import control
import control.flatsys

# List of functions that we can skip testing (special cases)
function_skiplist = [
    control.ControlPlot.reshape,                # needed for legacy interface
    control.phase_plot,                         # legacy function
    control.drss,                               # documention in rss
    control.frd,                                # tested separately below
    control.ss,                                 # tested separately below
    control.tf,                                 # tested separately below
]

# Checksums to use for checking whether a docstring has changed
function_docstring_hash = {
    control.append:                     '1bddbac0fe932755c85e9fb0bfb97d88',
    control.describing_function_plot:   '95f894706b1d3eeb3b854934596af09f',
    control.dlqe:                       'e1e9479310e4e5a6f50f5459fb3d2dfb',
    control.dlqr:                       '56d7f3a452bc8d7a7256a52d9d1dcb37',
    control.lqe:                        '0447235d11b685b9dfaf485dd01fdb9a',
    control.lqr:                        'a3e0a85f781fc9c0f69a4b7da4f0bd22',
    control.margin:                     'f02b3034f5f1d44ce26f916cc3e51600',
    control.parallel:                   'bfc470aef75dbb923f9c6fb8bf3c9b43',
    control.series:                     '9aede1459667738f05cf4fc46603a4f6',
    control.ss2tf:                      'e779b8d70205bc1218cc2a4556a66e4b',
    control.tf2ss:                      '086a3692659b7321c2af126f79f4bc11',
    control.markov:                     'a4199c54cb50f07c0163d3790739eafe',
    control.gangof4:                    'f9673ae4c6d26c202060ed4b9ef54800',
}

# List of keywords that we can skip testing (special cases)
keyword_skiplist = {
    control.input_output_response: ['method'],
    control.nyquist_plot: ['color'],                        # separate check
    control.optimal.solve_ocp: ['method', 'return_x'],      # deprecated
    control.sisotool: ['kvect'],                            # deprecated
    control.nyquist_response: ['return_contour'],           # deprecated
    control.create_estimator_iosystem: ['state_labels'],    # deprecated
    control.bode_plot: ['sharex', 'sharey', 'margin_info'], # deprecated
    control.eigensys_realization: ['arg'],                  # quasi-positional
    control.find_operating_point: ['method'],               # internal use
    control.zpk: ['args'],                                  # 'dt' (manual)
    control.StateSpace.dynamics: ['params'],                # not allowed
    control.StateSpace.output: ['params'],                  # not allowed
    control.flatsys.point_to_point: [
        'method', 'options',                                # minimize_kwargs
    ],
    control.flatsys.solve_flat_ocp: [
        'method', 'options',                                # minimize_kwargs
    ],
    control.optimal.OptimalControlProblem.compute_trajectory: [
        'return_x',                                         # legacy
    ],
    control.optimal.OptimalEstimationProblem.create_mhe_iosystem: [
        'inputs', 'outputs', 'states',                      # doc'd elsewhere
    ],
}

# Decide on the level of verbosity (use -rP when running pytest)
verbose = 1

@pytest.mark.parametrize("module, prefix", [
    (control, ""), (control.flatsys, "flatsys."),
    (control.optimal, "optimal."), (control.phaseplot, "phaseplot.")
])
def test_parameter_docs(module, prefix):
    checked = set()             # Keep track of functions we have checked

    # Look through every object in the package
    _info(f"Checking module {module}", 0)
    for name, obj in inspect.getmembers(module):
        _info(f"Checking object {name}", 4)

        # Parse the docstring using numpydoc
        doc = None if obj is None else npd.FunctionDoc(obj)

        # Skip anything that is outside of this module
        if inspect.getmodule(obj) is not None and \
           not inspect.getmodule(obj).__name__.startswith('control'):
            # Skip anything that isn't part of the control package
            continue

        # Skip non-top-level functions without parameter lists
        if prefix != "" and inspect.getmodule(obj) != module and \
           doc is not None and doc["Parameters"] == []:
            _info(f"skipping {prefix}.{name}", 2)
            continue

        if inspect.isclass(obj):
            _info(f"Checking class {name}", 1)
            # Check member functions within the class
            test_parameter_docs(obj, prefix + name + '.')

        if inspect.isfunction(obj):
            # Skip anything that is inherited, hidden, deprecated, or checked
            if inspect.isclass(module) and name not in module.__dict__ \
               or name.startswith('_') or obj in function_skiplist or \
               obj in checked:
                continue
            else:
                checked.add(obj)

            # Get the docstring (skip w/ warning if there isn't one)
            _info(f"Checking function {name}", 2)
            if obj.__doc__ is None:
                _warn(f"{module.__name__}.{name} is missing docstring", 2)
                continue
            else:
                docstring = inspect.getdoc(obj)
                source = inspect.getsource(obj)

            # Skip deprecated functions
            if ".. deprecated::" in docstring:
                _info("  [deprecated]", 2)
                continue
            elif re.search(name + r"(\(\))? is deprecated", docstring) or \
                 "function is deprecated" in docstring:
                _info("  [deprecated, but not numpydoc compliant]", 2)
                _warn(f"{name} deprecated, but not numpydoc compliant", 0)
                continue

            elif re.search(name + r"(\(\))? is deprecated", source):
                _warn(f"{name} is deprecated, but not documented", 1)
                continue

            # Get the signature for the function
            sig = inspect.signature(obj)

            # Go through each parameter and make sure it is in the docstring
            for argname, par in sig.parameters.items():

                # Look for arguments that we can skip
                if argname == 'self' or argname[0] == '_' or \
                   obj in keyword_skiplist and argname in keyword_skiplist[obj]:
                    continue

                # Check for positional arguments
                if par.kind == inspect.Parameter.VAR_POSITIONAL:
                    if obj in function_docstring_hash:
                        import hashlib
                        hash = hashlib.md5(
                            (docstring + source).encode('utf-8')).hexdigest()
                        if function_docstring_hash[obj] != hash:
                            _fail(
                                f"source/docstring for {name}() modified; "
                                f"recheck docstring and update hash to "
                                f"{hash=}")
                        continue

                    # Too complicated to check
                    if f"*{argname}" not in docstring:
                        _warn(
                            f"{name} {argname} has positional arguments; "
                            "docstring not checked")
                    continue

                # Check for keyword arguments (then look at code for parsing)
                elif par.kind == inspect.Parameter.VAR_KEYWORD:
                    # See if we documented the keyward argument directly
                    # if f"**{argname} :" in docstring:
                    #     continue

                    # Look for direct kwargs argument access
                    kwargnames = set()
                    for _, kwargname in re.findall(
                            argname + r"(\[|\.pop\(|\.get\()'([\w]+)'",
                            source):
                        _info(f"Found direct keyword argument {kwargname}", 2)
                        kwargnames.add(kwargname)

                    # Look for kwargs accessed via _get_param
                    for kwargname in re.findall(
                            r"_get_param\(\s*'\w*',\s*'([\w]+)',\s*" + argname,
                            source):
                        _info(f"Found config keyword argument {kwargname}", 2)
                        kwargnames.add(kwargname)

                    # Look for kwargs accessed via _process_legacy_keyword
                    for kwargname in re.findall(
                            r"_process_legacy_keyword\([\s]*" + argname +
                            r",[\s]*'[\w]+',[\s]*'([\w]+)'", source):
                        _info(f"Found legacy keyword argument {kwargname}", 2)
                        kwargnames.add(kwargname)

                    for kwargname in kwargnames:
                        if obj in keyword_skiplist and \
                           kwargname in keyword_skiplist[obj]:
                            continue
                        _info(f"Checking keyword argument {kwargname}", 3)
                        _check_parameter_docs(
                            name, kwargname, inspect.getdoc(obj),
                            prefix=prefix)

                # Make sure this argument is documented properly in docstring
                else:
                    _info(f"    Checking argument {argname}", 3)
                    _check_parameter_docs(
                        name, argname, docstring, prefix=prefix)

            # Look at the return values
            for val in doc["Returns"]:
                if val.name == '' and \
                   (match := re.search("([\w]+):", val.type)) is not None:
                    retname = match.group(1)
                    _warn(f"{obj.__name__} '{retname}' docstring missing space")


@pytest.mark.parametrize("module, prefix", [
    (control, ""), (control.flatsys, "flatsys."),
    (control.optimal, "optimal."), (control.phaseplot, "phaseplot.")
])
def test_deprecated_functions(module, prefix):
    checked = set()             # Keep track of functions we have checked

    # Look through every object in the package
    for name, obj in inspect.getmembers(module):
        # Skip anything that is outside of this module
        if inspect.getmodule(obj) is not None and (
                not inspect.getmodule(obj).__name__.startswith('control')
                or prefix != "" and inspect.getmodule(obj) != module):
            # Skip anything that isn't part of the control package
            continue

        if inspect.isclass(obj):
            # Check member functions within the class
            test_deprecated_functions(obj, prefix + name + '.')

        if inspect.isfunction(obj):
            # Skip anything that is inherited, hidden, or checked
            if inspect.isclass(module) and name not in module.__dict__ \
               or name[0] == '_' or obj in checked:
                continue
            else:
                checked.add(obj)

            # Get the docstring (skip w/ warning if there isn't one)
            if obj.__doc__ is None:
                _warn(f"{module.__name__}.{name} is missing docstring")
                continue
            else:
                docstring = inspect.getdoc(obj)
                source = inspect.getsource(obj)

            # Look for functions marked as deprecated in doc string
            if ".. deprecated::" in docstring:
                # Make sure a FutureWarning is issued
                if not re.search("FutureWarning", source):
                    _fail(f"{name} deprecated but does not issue FutureWarning")
            else:
                if re.search(name + r"(\(\))? is deprecated", docstring) or \
                   re.search(name + r"(\(\))? is deprecated", source):
                    _fail(
                        f"{name} deprecated but w/ non-standard docs/warnings")
                assert name != 'ss2io'

#
# Tests for I/O system classes
#
# The tests below try to make sure that we document I/O system classes
# and the factory functions that create them in a uniform way.
#

ct = control
fs = control.flatsys

# Dictionary of factory functions associated with primary classes
class_factory_function = {
    fs.FlatSystem: fs.flatsys,
    ct.FrequencyResponseData: ct.frd,
    ct.InterconnectedSystem: ct.interconnect,
    ct.LinearICSystem: ct.interconnect,
    ct.NonlinearIOSystem: ct.nlsys,
    ct.StateSpace: ct.ss,
    ct.TransferFunction: ct.tf,
}

#
# List of arguments described in class docstrings
#
# These are the minimal arguments needed to initialize the class.  Optional
# arguments should be documented in the factory functions and do not need
# to be duplicated in the class documentation.
#
class_args = {
    fs.FlatSystem: ['forward', 'reverse'],
    ct.FrequencyResponseData: ['response', 'omega', 'dt'],
    ct.NonlinearIOSystem: [
        'updfcn', 'outfcn', 'inputs', 'outputs', 'states', 'params', 'dt'],
    ct.StateSpace: ['A', 'B', 'C', 'D', 'dt'],
    ct.TransferFunction: ['num', 'den', 'dt'],
}

#
# List of attributes described in class docstrings
#
# This is the list of attributes for the class that are not already listed
# as parameters used to initialize the class.  These should all be defined
# in the class docstring.
#
# Attributes that are part of all I/O system classes should be listed in
# `std_class_attributes`.  Attributes that are not commonly needed are
# defined as part of a parent class can just be documented there, and
# should be listed in `iosys_parent_attributes` (these will be searched
# using the MRO).

std_class_attributes = [
    'ninputs', 'noutputs', 'input_labels', 'output_labels', 'name', 'shape']

# List of attributes defined for specific I/O systems
class_attributes = {
    fs.FlatSystem: [],
    ct.FrequencyResponseData: [],
    ct.NonlinearIOSystem: ['nstates', 'state_labels'],
    ct.StateSpace: ['nstates', 'state_labels'],
    ct.TransferFunction: [],
}

# List of attributes defined in a parent class (no need to warn)
iosys_parent_attributes = [
    'input_index', 'output_index', 'state_index',       # rarely used
    'states', 'nstates', 'state_labels',                # not need in TF, FRD
    'params', 'outfcn', 'updfcn'                        # NL I/O, SS overlap
]

#
# List of arguments described (only) in factory function docstrings
#
# These lists consist of the arguments that should be documented in the
# factory functions and should not be duplicated in the class
# documentation, even though in some cases they are actually processed in
# the class __init__ function.
#
std_factory_args = [
    'inputs', 'outputs', 'name', 'input_prefix', 'output_prefix']

factory_args = {
    fs.flatsys: ['states', 'state_prefix'],
    ct.frd: ['sys'],
    ct.nlsys: ['state_prefix'],
    ct.ss: ['sys', 'states', 'state_prefix'],
    ct.tf: ['sys'],
}


@pytest.mark.parametrize(
    "cls, fcn, args",
    [(cls, class_factory_function[cls], class_args[cls])
     for cls in class_args.keys()])
def test_iosys_primary_classes(cls, fcn, args):
    docstring = inspect.getdoc(cls)

    # Make sure the typical arguments are there
    for argname in args + std_class_attributes + class_attributes[cls]:
        _check_parameter_docs(cls.__name__, argname, docstring)

    # Make sure we reference the factory function
    if re.search(
            r"created.*(with|by|using).*the[\s]*"
            f":func:`~control\\..*{fcn.__name__}`"
            r"[\s]factory[\s]function", docstring, re.DOTALL) is None:
        pytest.fail(
            f"{cls.__name__} does not reference factory function "
            f"{fcn.__name__}")

    # Make sure we don't reference parameters from the factory function
    for argname in factory_args[fcn]:
        if re.search(f"[\\s]+{argname}(, .*)*[\\s]*:", docstring) is not None:
            pytest.fail(
                f"{cls.__name__} references factory function parameter "
                f"'{argname}'")


@pytest.mark.parametrize("cls", class_args.keys())
def test_iosys_attribute_lists(cls, ignore_future_warning):
    fcn = class_factory_function[cls]

    # Create a system that we can scan for attributes
    sys = ct.rss(2, 1, 1)
    ignore_args = []
    match fcn:
        case ct.tf:
            sys = ct.tf(sys)
            ignore_args = ['state_labels']
        case ct.frd:
            sys = ct.frd(sys, [0.1, 1, 10])
            ignore_args = ['state_labels']
        case ct.nlsys:
            sys = ct.nlsys(sys)
        case fs.flatsys:
            sys = fs.flatsys(sys)
            sys = fs.flatsys(sys.forward, sys.reverse)

    docstring = inspect.getdoc(cls)
    for name, obj in inspect.getmembers(sys):
        if name.startswith('_') or inspect.ismethod(obj) or name in ignore_args:
            # Skip hidden variables; class methods are checked elsewhere
            continue

        # Try to find documentation in primary class
        if _check_parameter_docs(
                cls.__name__, name, docstring, fail_if_missing=False):
            continue

        # Couldn't find in main documentation; look in parent classes
        for parent in cls.__mro__:
            if parent == object:
                pytest.fail(
                    f"{cls.__name__} attribute '{name}' not documented")

            if _check_parameter_docs(
                    parent.__name__, name, inspect.getdoc(parent),
                    fail_if_missing=False):
                if name not in iosys_parent_attributes + factory_args[fcn]:
                    warnings.warn(
                        f"{cls.__name__} attribute '{name}' only documented "
                        f"in parent class {parent.__name__}")
                break


@pytest.mark.parametrize("cls", [ct.InputOutputSystem, ct.LTI])
def test_iosys_container_classes(cls):
    # Create a system that we can scan for attributes
    sys = cls(states=2, outputs=1, inputs=1)

    docstring = inspect.getdoc(cls)
    for name, obj in inspect.getmembers(sys):
        if name.startswith('_') or inspect.ismethod(obj):
            # Skip hidden variables; class methods are checked elsewhere
            continue

        # Look through all classes in hierarchy
        if verbose:
            print(f"{name=}")
        for parent in cls.__mro__:
            if parent == object:
                pytest.fail(
                    f"{cls.__name__} attribute '{name}' not documented")

            if verbose:
                print(f"  {parent=}")
            if _check_parameter_docs(
                    parent.__name__, name, inspect.getdoc(parent),
                    fail_if_missing=False):
                break


@pytest.mark.parametrize("cls", [ct.InterconnectedSystem, ct.LinearICSystem])
def test_iosys_intermediate_classes(cls):
    docstring = inspect.getdoc(cls)

    # Make sure there is not a parameters section
    if re.search(r"\nParameters\n----", docstring) is not None:
        pytest.fail(f"intermediate {cls} docstring contains Parameters section")

    # Make sure we reference the factory function
    fcn = class_factory_function[cls]
    if re.search(f":func:`~control.{fcn.__name__}`", docstring) is None:
        pytest.fail(
            f"{cls.__name__} does not reference factory function "
            f"{fcn.__name__}")


@pytest.mark.parametrize("fcn", factory_args.keys())
def test_iosys_factory_functions(fcn):
    docstring = inspect.getdoc(fcn)
    cls = list(class_factory_function.keys())[
        list(class_factory_function.values()).index(fcn)]

    # Make sure we reference parameters in class and factory function docstring
    for argname in class_args[cls] + std_factory_args + factory_args[fcn]:
        _check_parameter_docs(fcn.__name__, argname, docstring)

    # Make sure we don't reference any class attributes
    for argname in std_class_attributes + class_attributes[cls]:
        if argname in std_factory_args:
            continue
        if re.search(f"[\\s]+{argname}(, .*)*[\\s]*:", docstring) is not None:
            pytest.fail(
                f"{fcn.__name__} references class attribute '{argname}'")


# Utility function to check for an argument in a docstring
def _check_parameter_docs(
        funcname, argname, docstring, prefix="", fail_if_missing=True):
    funcname = prefix + funcname

    # Find the "Parameters" section of docstring, where we start searching
    # TODO: rewrite to use numpydoc
    if not (match := re.search(r"\nParameters\n----", docstring)):
        if fail_if_missing:
            _fail(f"{funcname} docstring missing Parameters section")
        else:
            return False
    else:
        start = match.start()

    # Find the "Returns" section of the docstring (to be skipped, if present)
    match_returns = re.search(r"\nReturns\n----", docstring)

    # Find the "Other Parameters" section of the docstring, if present
    match_other = re.search(r"\nOther Parameters\n----", docstring)

    # Remove the returns section from docstring, in case output arguments
    # match input argument names (it happens...)
    if match_other and match_returns:
        docstring = docstring[start:match_returns.start()] + \
            docstring[match_other.start():]
    else:
        docstring = docstring[start:]

    # Look for the parameter name in the docstring
    if match := re.search(
            "\n" + r"((\w+|\.{3}), )*" + argname + r"(, (\w+|\.{3}))*:",
            docstring):
        # Found the string, but not in numpydoc form
        _warn(f"{funcname}: {argname} docstring missing space")

    elif not (match := re.search(
            "\n" + r"((\w+|\.{3}), )*" + argname + r"(, (\w+|\.{3}))* :",
            docstring)):
        if fail_if_missing:
            _fail(f"{funcname} '{argname}' not documented")
            pytest.fail(f"{funcname} '{argname}' not documented")
        else:
            _info(f"{funcname} '{argname}' not documented")
            return False

    # Make sure there isn't another instance
    second_match = re.search(
            "\n" + r"((\w+|\.{3}), )*" + argname + r"(, (\w+|\.{3}))*[ ]*:",
            docstring[match.end():])
    if second_match:
        _fail(f"{funcname} '{argname}' documented twice")

    return True


# Utility function to warn with verbose output
def _info(str, level=0):
    if verbose > level:
        print("  " * level + str)

def _warn(str, level=0):
    if verbose > level:
        print("  " * level + str)
    warnings.warn(str)

def _fail(str, level=0):
    if verbose > level:
        print("  " * level + str)
    pytest.fail(str)
