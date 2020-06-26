#!/usr/bin/env python
'''
    Many PPP functions were designed to automatically assign relevant populations 
    and/or individuals using a *Model* file. To enable this functionality, the 
    model_creator.py function may be used to produce *Model* files by either: i) 
    manually entering the necessary information or ii) by using files with the 
    relevant information. It is also all possible to create multiple models 
    simultaneously and assign populations to more than a single model. 

    .. image:: ../../PPP_assets/PPP_Model.png
        :width: 100 %
        :align: center

    A simple way to visualize models are as a hierarchy. Each *Model* may contain 
    one or more *Populations* and each *Population* may contain one or more 
    *Individuals*.

    ##################
    Command-line Usage
    ##################
    The model creator may be called using the following command:

    .. code-block:: bash
        
        model_creator.py

    ***********************
    Example 1: Simple Model
    ***********************
    A basic model only require a single population (pop) with a single in individual (ind).
    Only three commands are required:
    1) Create and name a model: *--model 1Pop_Model*
    2) Assign a pop to a model: *--model-pop 1Pop_Model Pop1*
    2) Assign an ind to a pop:  *--pop-ind Pop1 Ind1*

    .. code-block:: bash

        model_creator.py --model 1Pop_Model --model-pop Test Pop1 --pop-ind Pop1 Ind1
        
    ****************************
    Example 2: Model Using Files
    ****************************
    A model may also be created using two file options
    1) Assign multiple pops to model: *--model-pop-file 2Pop_Model 2Pops.txt*
    2) Assign multiple inds to pop:   *--pop-ind-file Pop1 Pop1_Inds.txt*
                                      *--pop-ind-file Pop2 Pop2_Inds.txt*

    .. code-block:: bash
        
        model_creator.py --model-pop-file 2Pop_Model 2Pops.txt --pop-ind-file Pop1 Pop1_Inds.txt --pop-ind-file Pop2 Pop2_Inds.txt

    .. code-block:: bash
       :caption: 2Pops.txt

       Pop1
       Pop2

    .. code-block:: bash
       :caption: Pop1_Inds.txt

       Ind1
       Ind2

    .. code-block:: bash
       :caption: Pop2_Inds.txt

       Ind3
       Ind4

    ############################
    Model Command-line Arguments
    ############################
    All model-based arguments may be used multiple times.

    **--model** *<model_str>*
        Argument used to define the name of a model to create.
    **--model-tree** *<model_str>* *<newick_str>*
        Argument used to assign a population tree to a model, in Newick format. 
        --eigenstrat-prefix.
    **--model-tree-file** *<model_str>* *<newick_file>*
        Argument used to assign a population tree file to a model, in Newick 
        format.
    **--model-pop** *<model_str>* *<pop_str>*
        Argument used to assign a population to a model.
    **--model-pops** *<model_str>* *<pop1_str>* *<pop2_str>* ..
        Argument used to assign a multiple populations to a model.
    **--model-pop-file** *<model_str>* *<pop_file>*
        Argument used to assign a multiple populations to a model using a file.
    **--pop-ind** *<pop_str>* *<ind_str>*
        Argument used to assign a individual to a population.
    **--pop-inds** *<pop_str>* *<ind1_str>* *<ind2_str>* ..
        Argument used to assign a multiple individuals to a population.
    **--pop-ind-file** *<pop_str>* *<ind_file>*
        Argument used to assign a multiple individuals to a population using a file.

    #############################
    Output Command-line Arguments
    #############################
    **--out** *<output_filename>*
        Argument used to define the complete output filename.
    **--overwrite**
        Argument used to define if previous output should be overwritten.
'''

import os
import sys
import json
import argparse
import logging
import itertools

from collections import defaultdict, OrderedDict

from pgpipe.model import Model, ModelFile, write_model_file
from pgpipe.logging_module import initLogger, logArgs


def model_creator_parser (passed_arguments):
    '''VCF Argument Parser - Assigns arguments from command line'''

    def parser_dict_list_append ():
        '''Custom action to house data as defaultdict list'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):
                if getattr(args, self.dest):
                    if values[1] not in getattr(args, self.dest)[values[0]]:
                        # Append the argument with the file
                        getattr(args, self.dest)[values[0]].append(values[1])
                else:
                    # Set the argument with the file (as list)
                    arg_dict = defaultdict(list)
                    arg_dict[values[0]].append(values[1])
                    setattr(args, self.dest, arg_dict)
        return customAction

    def parser_dict_list_extend ():
        '''Custom action to house data as defaultdict list'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):
                if getattr(args, self.dest):
                    for value in values[1:]:
                        if value not in getattr(args, self.dest)[values[0]]:
                            # Append the argument with the file
                            getattr(args, self.dest)[values[0]].append(value)
                else:
                    # Set the argument with the file (as list)
                    arg_dict = defaultdict(list)
                    arg_dict[values[0]].extend(values[1:])
                    setattr(args, self.dest, arg_dict)
        return customAction

    def parser_dict_str ():
        '''Custom action to house data as defaultdict int'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):
                # Assign the passed value
                if getattr(args, self.dest):
                    # Append the argument with the file
                    getattr(args, self.dest)[values[0]] = values[1]

                else:
                    # Set the argument with the file (as list)
                    arg_dict = defaultdict(str)
                    arg_dict[values[0]] = values[1]
                    setattr(args, self.dest, arg_dict)
        return customAction

    def parser_dict_int ():
        '''Custom action to house data as defaultdict int'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):

                # Check the passed value is an int
                try:
                    int(values[1])
                except:
                    raise Exception('--%s only accepts integers' % self.dest)

                # Assign the passed value
                if getattr(args, self.dest):
                    # Append the argument with the file
                    getattr(args, self.dest)[values[0]] = int(values[1])

                else:
                    # Set the argument with the file (as list)
                    arg_dict = defaultdict(int)
                    arg_dict[values[0]] = int(values[1])
                    setattr(args, self.dest, arg_dict)
        return customAction

    def parser_dict_file ():
        '''Custom action to house data as defaultdict int'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):

                if not os.path.isfile(values[1]):
                    raise IOError('%s not found' % values[1])

                # Assign the passed value
                if getattr(args, self.dest):
                    # Append the argument with the file
                    getattr(args, self.dest)[values[0]] = values[1]

                else:
                    # Set the argument with the file (as list)
                    arg_dict = defaultdict(str)
                    arg_dict[values[0]] = values[1]
                    setattr(args, self.dest, arg_dict)
        return customAction

    def metavar_list (var_list):
        '''Create a formmated metavar list for the help output'''
        return '{' + ', '.join(var_list) + '}'

    model_parser = argparse.ArgumentParser(formatter_class = argparse.ArgumentDefaultsHelpFormatter)

    # General model arguments
    model_parser.add_argument('--model', help = 'Defines the name of a model', type = str, action = 'append', required = True)

    # Tree arguments
    model_parser.add_argument('--model-tree', metavar = ('MODEL', 'TREE'), help = 'Assign population tree string to a model, in Newick format', type = str, nargs = 2, action = parser_dict_str())
    model_parser.add_argument('--model-tree-file',  metavar = ('MODEL', 'NEWICK_FILE'), help = 'Assign population tree file to a model, in Newick format', type = str, nargs = 2, action = parser_dict_file())

    # Population arguments
    model_parser.add_argument('--model-pop', metavar = ('MODEL', 'POP'), dest = 'pops', help = 'Assign a population name to a model', type = str, nargs = 2, action = parser_dict_list_append())
    model_parser.add_argument('--model-pops', metavar = ('MODEL', 'POP'), dest = 'pops', help = 'Assign multiple population names to a model', type = str, nargs = '+', action = parser_dict_list_extend())
    model_parser.add_argument('--model-pop-file', metavar = ('MODEL', 'POP_FILE'), help = 'Assign multiple population names to a model usign a file', type = str, nargs = 2, action = parser_dict_file())

    # Individual arguments
    model_parser.add_argument('--pop-ind', metavar = ('POP', 'IND'), dest = 'inds', help = 'Assign an individual name to a population', type = str, nargs = 2, action = parser_dict_list_append())
    model_parser.add_argument('--pop-inds', metavar = ('POP', 'IND'), dest = 'inds', help = 'Assign multiple individual names to a population', type = str, nargs = '+', action = parser_dict_list_extend())
    model_parser.add_argument('--pop-ind-file', metavar = ('POP', 'IND_FILE'), help = 'Assign multiple individual names to a population using a file', type = str, nargs = 2, action = parser_dict_file())

    # Output Arguments
    model_parser.add_argument('--out', help = 'Specifies the complete output filename.', type = str, default = 'out.model')
    model_parser.add_argument('--overwrite', help = "Specifies if previous output files should be overwritten", action = 'store_true')

    if passed_arguments:
        return model_parser.parse_args(passed_arguments)
    else:
        return model_parser.parse_args()

def incompatible_duplicates_check (term, *arguments_to_test):

    # Duplicate count
    duplicates_count = 0

    # Loop the passed arguments
    for argument_to_test in arguments_to_test:

        # Check if the argument has been populated
        if argument_to_test:

            # Check if the argument has the term
            if term in argument_to_test:

                # Add to the duplicate count if the incompatible term is found
                duplicates_count += 1

    # Check if there were duplicates_count
    if duplicates_count > 1:
        return True
    else:
        return False

def assigment_check (term, *arguments_to_be_assigned):

    # Term assignment boolean
    term_assigned = False

    # Loop the passed arguments
    for argument_to_be_assigned in arguments_to_be_assigned:

        # Check if the argument has been populated
        if argument_to_be_assigned:

            # Check if the argument has the term
            if term in argument_to_be_assigned:

                # Mark the term assigned
                term_assigned = True

    # Return the boolean
    return term_assigned

def dict_argument_to_list (term, list_argument):

    # Check if either the argument or term was not assigned
    if not list_argument or term not in list_argument:
        return []

    # Return data as list
    return list_argument[term]

def file_dict_argument_to_list (term, file_argument):

    # Check if either the argument or term was not assigned
    if not file_argument or term not in file_argument:
        return []

    # List to hold the file data
    data_list = []

    # Check if running via python 3
    if sys.version_info[0] == 3:

        # Open the file and save the data
        with open(file_argument[term], 'r') as data_file:
            for data_line in data_file:
                data_list.append(data_line.strip())

    # Check if running via python 2
    else:

        # Open the file and save the data
        with open(file_argument[term], 'rb') as data_file:
            for data_line in data_file:
                data_list.append(data_line.strip())

    # Return data as list
    return data_list

def run (passed_arguments = []):
    '''

    Parameters
    ----------
    --model : str
        Name of the model
    --model-tree : str, str
        Assign newick-formatted population tree to model
        Example: --model-tree model_name newick_tree
    --model-tree-file : str, str
        Assign newick-formatted population tree file to model
        Example: --model-tree-file model_name newick_file
    --model-pop : str, str
        Assign single population name to a model
        Example: --model-pop model_name pop_name
    --model-pops : str, list
        Assign multiple population names to a model
        Example: --model-pops model_name pop_name1 pop_name2 etc.
    --model-pop-file : str, str
        Assign population names to a model using a file
        Example: --model-pop-file model_name pop_file
    --pop-ind : str, str
        Assign single individual name to a population
        Example: --pop-ind pop_name ind_name
    --pop-inds : str, list
        Assign multiple population names to a model
        Example: --pop-inds pop_name ind_name1 ind_name2 etc.
    --pop-ind-file : str, str
        Assign population names to a model using a file
        Example: --pop-ind-file pop_name ind_file
    --out : str
        Filename of the model output

    Returns
    -------

    Raises
    ------
    Exception
        No tree assigned to model
    Exception
        Multiple trees assigned to model
    Exception
        No population assigned to model
    Exception
        No individuals assigned to population
    '''

    # Grab VCF arguments from command line
    creator_args = model_creator_parser(passed_arguments)

    # Adds the arguments (i.e. parameters) to the log file
    logArgs(creator_args, 'model_creator')

    # Create the model file
    model_file = ModelFile()

    # Loop each model specified to confirm parameters are valid
    for model in creator_args.model:

        # Check that a tree has been assigned to the model
        if not assigment_check(model, creator_args.model_tree_file, creator_args.model_tree):
            logging.warning('No tree assigned to %s' % model)

        # Check that multiple trees have not been assigned to the model
        if incompatible_duplicates_check(model, creator_args.model_tree_file, creator_args.model_tree):
            raise Exception('Multiple trees assigned to %s' % model)

        # Check if a pop assignment arguments has been used
        if not assigment_check(model, creator_args.pops, creator_args.model_pop_file):
            raise Exception('No populations assigned to %s' % model)

        # Create the model
        model_data = Model(name = model)

        logging.info('Model (%s) created' % model)

        # Convert the inds dict into a list
        pop_list = dict_argument_to_list(model, creator_args.pops)

        # Convert the pop file into a list
        pop_file_list = file_dict_argument_to_list(model, creator_args.model_pop_file)

        # Combine the pop arguments
        combined_pops = list(set(pop_list + pop_file_list))

        logging.info('Populations assigned for model (%s)' % model)

        # Assign the tree
        model_data.assign_tree(tree = '')

        # Loop each population in the model
        for pop in combined_pops:

            # Check if a individual assignment arguments has been used
            if not assigment_check(pop, creator_args.inds, creator_args.pop_ind_file):
                raise Exception('No individuals assigned to %s' % pop)

            # Convert the inds dict into a list
            ind_list = dict_argument_to_list(pop, creator_args.inds)

            # Convert the inds file into a list
            ind_file_list = file_dict_argument_to_list(pop, creator_args.pop_ind_file)

            # Combine the pop arguments
            combined_inds = list(set(ind_list + ind_file_list))

            logging.info('Individuals assigned for population (%s)' % pop)

            # Assign the population
            model_data.assign_pop(pop = pop, inds = combined_inds)

            logging.info('Model (%s) assigned to model file' % model)

        # Add the model to the model file
        model_file[model] = model_data

    # Create the model file
    write_model_file(model_file, creator_args.out, overwrite = creator_args.overwrite)


if __name__ == "__main__":
    initLogger()
    run()
