# Copyright (C) 2002, Thomas Hamelryck (thamelry@binf.ku.dk)
# This code is part of the Biopython distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.

"""The structure class, representing a macromolecular structure."""

from Bio.PDB.Entity import Entity


class Structure(Entity):
    """
    The Structure class contains a collection of Model instances.
    """
    def __init__(self, id):
        self.level="S"
        Entity.__init__(self, id)

    # Special methods

    def __repr__(self):
        return "<Structure id=%s>" % self.get_id()

    # Private methods

    def _sort(self, m1, m2):
        """Sort models.

        This sorting function sorts the Model instances in the Structure instance.
        The sorting is done based on the model id, which is a simple int that
        reflects the order of the models in the PDB file.

        Arguments:
        o m1, m2 - Model instances
        """
        return cmp(m1.get_id(), m2.get_id())

    # Public

    def get_chains(self):
        for m in self:
            for c in m:
                yield c

    def get_residues(self):
        for c in self.get_chains():
            for r in c:
                yield r

    def get_atoms(self):
        for r in self.get_residues():
            for a in r:
                yield a

    def renumber_residues(self, init=1, consecutive_chains=0):
        """ Renumbers residues in a structure starting from init (default: 1).
            Keeps numbering consistent with gaps if they exist in the original numbering.

            Options:
            init [int] (default: 1)
            Starts residue numbering from this number.

            consecutive_chains [int] (default: 0)
            Renumbers first residue of chain i+1 after last residue of chain i skipping
            <consecutive_chains> numbers between chains.
        """
        r = init # Residue init
        h = 0 # hetatm init
        for model in self:
            for chain in model:
                r_new, h_new = chain.renumber_residues(res_init=r, het_init=h)
                if consecutive_chains:
                    r = r_new + consecutive_chains
                    h = h_new + consecutive_chains

    def build_biological_unit(self):
        """ Uses information from header (REMARK 350) to build full biological
            unit assembly.
            Each new subunit is added to the structure as a new MODEL record.
            Identity matrix is ignored.
            Returns an integer with the number of matrices used.
        """

        from copy import deepcopy # To copy structure object
        if self.header['biological_unit']:
            biomt_data = self.header['biological_unit'][1:] # 1st is identity
        else:
            raise ValueError( "REMARK 350 field missing in the PDB file")

        temp = [] # container for new models
        seed = 0 # Seed for model numbers

        for transformation in biomt_data:
            M = [i[:-1] for i in transformation] # Rotation Matrix
            T = [i[-1] for i in transformation] # Translation Vector
            model = deepcopy(self.child_list[0]) # Bottleneck...
            seed += 1
            model.id = seed
            for atom in model.get_atoms():
                atom.transform(M, T)
            temp.append(model)

        # Add MODELs to structure object
        map(self.add, temp)
        return seed

    def apply_transformation_matrix(self):
        """ Uses information from header (REMARK 350) to build full biological
            unit assembly.
            Returns a new Structure object with each subunit added as a new Model.
        """
        # Create new Structure object to hold translated/rotated subunits
        from Bio.PDB.StructureBuilder import StructureBuilder
        structure_builder=StructureBuilder()
        s = structure_builder.init_structure("BioUnit_"+self.id)
        structure_builder.init_seg(' ') # Empty Segment Id
        
        # Retrieve BIOMT Data
        if self.header['biological_unit']:
            biomt_data = self.header['biological_unit']
        else:
            raise ValueError( "REMARK 350 field missing in the PDB file")
        
        # Process BIOMT data and apply transformations
        for index, transformation in enumerate(biomt_data, start=1):
            structure_builder.init_model(index)
            M = [i[:-1] for i in transformation] # Rotation Matrix
            T = [i[-1] for i in transformation] # Translation Vector

            for chain in self.get_chains():
                structure_builder.init_chain(chain.id)
                for residue in chain:
                    structure_builder.init_residue(residue.resname, residue.id[0], residue.id[1], residue.id[2])
                    for atom in residue:
                        a = structure_builder.init_atom(atom.name, atom.coord, atom.bfactor, atom.occupancy, atom.altloc, atom.fullname, atom.serial_number, atom.element)
                        structure_builder.atom.transform(M, T)

        # Return new Structure Object
        return structure_builder.get_structure()

    def remove_disordered_atoms(self, keep_loc='A', verbose=False):
        """
        Substitutes DisorderedAtom objects for Atom object.
        Choice of Atom to keep defined by keep_loc argument.

        Originally based on the solution by Ramon Crehuet in the Biopython Wiki.
        http://www.biopython.org/wiki/Remove_PDB_disordered_atoms

        Arguments:

        - keep_loc, string, alternate location to keep (A has the highest occupancy). [A is default]
        - verbose, boolean, if True outputs info on each DisorderedAtom found.

        """

        substitutions = 0
        for residue in self.get_residues():
            disordered = [a for a in residue if a.is_disordered()]
            if disordered:
                substitutions += 1
                if verbose:
                    print "Residue %s:%s has %s disordered atoms: %s" % (residue.resname, residue.get_id()[1],
                                                                         len(disordered),
                                                                         '/'.join([ d.name for d in disordered ])
                                                                        )
                for atom in disordered:
                    try:
                        a = atom.disordered_get(keep_loc)
                    except KeyError: # Descriptive Enough
                        print "Atomic Position %s not found for %s (%s:%s)" % (keep_loc,
                                                                              atom,
                                                                              residue.resname,
                                                                              residue.get_id()[1])
                        continue
                    a.disordered_flag = 0
                    residue.detach_child(atom.name)
                    residue.add(a)
        return substitutions