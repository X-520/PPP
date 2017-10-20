import os
import sys
import subprocess
import argparse
import logging
import itertools

from collections import defaultdict

# Insert Jared's directory path, required for calling Jared's functions. Change when directory structure changes.
sys.path.insert(0, os.path.abspath(os.path.join(os.pardir, 'jared')))

from logging_module import initLogger


class Model:
    def __init__ (self, name):
        self.name = name
        self.tree = ''
        self.npop = 0
        self.pop_list = []
        self.nind = defaultdict(int)
        self.ind_dict = defaultdict(list)
        self.pop_files = []
        self.individuals_file = ''

    @property
    def ind_list(self):
        return itertools.chain.from_iterable(self.ind_dict.values())

    def assign_tree (self, tree):
        self.tree = tree

    def assign_pop (self, pop, inds = []):
        self.npop += 1
        self.pop_list.append(pop)
        if inds:
            self.nind[pop] = len(inds)
            self.ind_dict[pop] = inds

    def create_pop_files (self, file_ext = '', file_path = '', overwrite = False):
        for pop in self.pop_list:
            # Assign the filename for the population file
            pop_filename = pop + file_ext

            # If a path is assigned, create the file at the specified location
            if file_path:
                pop_filename = os.path.join(file_path, pop_filename)

            # Check if previous files should be overwriten
            if not overwrite:
                # Check if the file already exists
                if os.path.isfile(pop_filename):
                    raise IOError('Population file exists.')

            # Create the population file
            pop_file = open(pop_filename, 'w')
            pop_file.write('%s\n' %'\n'.join(self.ind_dict[pop]))
            pop_file.close()

            # Save the population filename
            self.pop_files.append(pop_filename)

    def delete_pop_files (self):
        # Check if pop files were created
        if len(self.pop_files) != 0:

            # Loop the created pop files
            for pop_file in self.pop_files:
                # Delete the pop file
                os.remove(pop_file)

            # Remove the filenames
            self.pop_files = []


    def create_individuals_file (self, file_ext = '', file_path = '', overwrite = False):
        # Assign the filename for the population file
        ind_filename = 'individual.keep' + file_ext

        # If a path is assigned, create the file at the specified location
        if file_path:
            ind_filename = os.path.join(file_path, ind_filename)

        # Check if previous files should be overwriten
        if not overwrite:
            # Check if the file already exists
            if os.path.isfile(ind_filename):
                raise IOError('Individuals file exists.')

        # Create the population file
        ind_file = open(ind_filename, 'w')
        ind_file.write('%s\n' %'\n'.join(self.ind_list))
        ind_file.close()

        # Save the individuals filename
        self.individuals_file = ind_filename

    def delete_individuals_file (self):
        # Check if an individuals file was created
        if self.individuals_file:

            # Delete the individuals file
            os.remove(self.individuals_file)
            
            # Remove the filename
            self.individuals_file = ''


def read_model_file (filename):

    # Used to store each model within the file
    models_in_file = {}

    # Used to store the current model
    current_model = None
    # Used to store the expected number of populations in a model.
    model_npop = 0
    # Used to store the current population name
    pop_name = ''
    # Used to store the expected number of individuals in a population.
    pop_nind = 0

    with open(filename, 'r') as model_file:
        for model_line in model_file:
            # Remove whitespace
            model_line = model_line.strip()

            if 'MODEL:' in model_line:

                # Check if previous model is stored
                if current_model != None:

                    # Make sure the population counts match
                    if current_model.npop != model_npop:
                        print 'Number of populations found in %s does not match NPOP' % current_model.name
                        sys.exit()

                    # Store model
                    models_in_file[current_model.name] = current_model

                    # Clear variables before next model
                    current_model = None
                    model_npop = 0

                # Create the model
                current_model = Model(model_line.split(':')[1].strip())

            elif 'TREE:' in model_line:
                # Assign the tree to the model
                current_model.assign_tree(model_line.split(':')[1].strip())

            elif 'NPOP:' in model_line:
                model_npop = int(model_line.split(':')[1].strip())

            elif 'POP:' in model_line:
                pop_name = model_line.split(':')[1].strip()

            elif 'NIND:' in model_line:
                pop_nind = int(model_line.split(':')[1].strip())

            elif 'INDS:' in model_line:
                # Get the list of individuals
                ind_list = [ind.strip() for ind in model_line.split(':')[1].split(',')]
                # Make sure the individual counts match
                if pop_nind != len(ind_list):
                    print 'Number of individuals specified in INDS does not match NIND'
                    sys.exit()

                # Assign the current population
                current_model.assign_pop(pop_name, ind_list)

                # Clear variables before next population/model
                pop_name = ''
                pop_nind = None

    # Make sure the population counts match
    if current_model.npop != model_npop:
        print 'Number of populations found in %s does not match NPOP' % current_model.name
        sys.exit()

    # Store model
    models_in_file[current_model.name] = current_model

    return models_in_file
