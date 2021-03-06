"""
Functions defined on Molecules.

@author: kkorovin@cs.cmu.edu

A list of examples of how add objective functions.
(Some are from rdkit, but new ones should be user-definable.)

NOTES:
* List of RDkit mol descriptors:
  https://www.rdkit.org/docs/GettingStartedInPython.html#list-of-available-descriptors

"""

from myrdkit import Chem
from rdkit_contrib.sascorer import calculateScore as calculateSAScore
from myrdkit import qed
from myrdkit import Descriptors

def get_objective_by_name(name):
    """Get a function computing molecular property.
    See individual functions below for descriptions.
    
    Arguments:
        name {str} -- one of "sascore", "logp", "qed"

    Returns:
        function: mol->float

    Raises:
        NotImplementedError -- function not implemented
    """
    if name == "sascore":
        return SAScore
    elif name == "logp":
        return LogP
    elif name == "qed":
        return QED
    else:
        raise NotImplementedError

def to_rdkit(mol):
    if isinstance(mol, list):
        rdkit_mol = mol[0].to_rdkit()
    else:
        rdkit_mol = mol.to_rdkit()
    return rdkit_mol

def SAScore(mol):
    """ Synthetic accessibility score """
    rdkit_mol = to_rdkit(mol)
    return calculateSAScore(rdkit_mol)

def LogP(mol):
    """ Range of LogP between [0, 5] corresponds to drug-like mols """
    rdkit_mol = to_rdkit(mol)
    return Descriptors.MolLogP(rdkit_mol)

def QED(mol):
    """ Quantative estimation of drug-likeliness.
    `High` ranges - [0.9, 1.]

    """
    rdkit_mol = to_rdkit(mol)
    return qed(rdkit_mol)

def SMILES_len(mol):
    return len(mol.smiles)


