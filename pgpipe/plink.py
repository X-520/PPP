import os
import sys
import subprocess
import shutil
import argparse
import glob
import copy
import logging
import re

# Call PPP-based scripts
#sys.path.insert(0, os.path.abspath(os.path.join(os.pardir,'pppipe')))

from pgpipe.vcf_reader_func import checkFormat
from pgpipe.bcftools import convert_vcf
from pgpipe.logging_module import initLogger, logArgs

def log_plink_reference (out_filename, append_mode = False, ref_header = True):

    # Check if the file is to be written in append mode
    if append_mode:

        # Open the file
        log_file = open(out_filename + '.log', 'a')

        # Check if the ref header should be added
        if ref_header:
            log_file.write('\nPlease Reference alongside the PPP:\n')

    else:

        # Open the file
        log_file = open(out_filename + '.log', 'w')

        # Check if the ref header should be added
        if ref_header:
            log_file.write('Please Reference alongside the PPP:\n')

    log_file.write('Chang, C. C. et al. Second-generation PLINK: Rising to ' 
                   'the challenge of larger and richer datasets. Gigascience ' 
                   '(2015). doi:10.1186/s13742-015-0047-8')
    log_file.close()

    logging.info('Reference assigned')

def assign_delim_from_ids (filename, id_column = 0, default_delim = '_'):

    delim_symbols = ['-', '|', '/', '@', '&', '*', '^', '%', '$']

    symbols_present = []

    with open(filename, 'rU') as sample_file:
        for line_pos, sample_line in enumerate(sample_file):
            if line_pos > 1:
                # Stores the current sample ID
                sample_id = sample_line.strip().split()[id_column]
                # Symbols found in the sample ID
                id_symbols = re.sub(r'[a-zA-Z0-9]','', sample_id)
                # Iterate the symbols from the ID
                for id_symbol in iter(id_symbols):
                    # Check if that symbol has been stored
                    if id_symbol not in symbols_present:
                        # Store symbols
                        symbols_present.append(id_symbol)

    if default_delim not in symbols_present:
        return default_delim
    else:
        for delim_symbol in delim_symbols:
            if delim_symbol not in symbols_present:
                return delim_symbol

    raise IOError('Cannot assign plink delimiter')

def assign_plink_output_args (out_prefix, out_format, overwrite = True):
    '''
        Assigns the output arguments

        Parameters
        ----------
        filename : str
            Specifies the input filename of unknown format

        Returns
        -------
        list
            Returns vcftools input command for `filename`

        Raises
        ------
        IOError
            If filename is an unknown file format
    '''
    # Check if previous output should be overwritten
    if not overwrite:

        # Check if the output is only a single file
        if out_format in ['vcf', 'vcf.gz', 'bcf']:

            # Save the filename of the expected output
            out_filename = out_prefix + '.' + out_format

            # Check if intermediate already exists
            if out_format == 'bcf':

                # Save the filename of the expected intermediate
                intermediate_filename = out_prefix + '.vcf.gz'
                raise Exception('%s intermediate exists. Add --overwrite to ignore' % intermediate_filename)

            # Check if the output already exists
            if os.path.isfile(out_filename):
                raise Exception('%s already exists. Add --overwrite to ignore' % out_filename)

        # Check if the output if a ped or bed file-set
        elif out_format in ['ped', 'binary-ped']:

            if out_format == 'ped':

                # List of the output suffixes for ped files
                out_suffixes = ['ped', 'map']

            elif out_format == 'binary-ped':

                # List of the output suffixes for bed files
                out_suffixes = ['bed', 'bim', 'fam']

            # Loop the suffixes
            for out_suffix in out_suffixes:

                # Save the filename of the expected output
                out_filename = out_prefix + '.' + out_suffix

                # Check if the output already exists
                if os.path.isfile(out_filename):
                    raise Exception('%s already exists. Add --overwrite to ignore' % out_filename)

    # Check if the output is only a single file
    if out_format in ['vcf', 'vcf.gz', 'bcf']:

        if out_format == 'vcf':
            return ['--recode', 'vcf-iid', '--out', out_prefix]

        if out_format == 'vcf.gz':
            return ['--recode', 'vcf-iid', 'bgz', '--out', out_prefix]

        if out_format == 'bcf':
            return ['--recode', 'vcf-iid', 'bgz', '--out', out_prefix]

    # Check if the output if a ped or bed file-set
    elif out_format in ['ped', 'binary-ped']:

        if out_format == 'ped':
            return ['--recode', '--out', out_prefix]

        if out_format == 'binary-ped':
            return ['--make-bed', '--out', out_prefix]

    else:
        raise IOError('Unknown file format. This error should NOT show up')

def assign_ped_from_files (ped_filename = None, map_filename = None, **kwargs):

    # Check if a bed file is assigned
    if not ped_filename:
        raise IOError('Unable to assign ped file. Please confirm the file is named correctly')

    # Check if bim and fam file are not assigned
    if not map_filename:
        raise IOError('Unable to assign map file. Please confirm the map file (i.e. --map) is assigned')

    # Return the ped associated args
    return ['--ped', ped_filename, '--map', map_filename]

def assign_ped_from_prefix (ped_prefix = None, **kwargs):

    # Check if the a prefix was assigned
    if not ped_prefix:
        raise IOError('No PED prefix specified. Please confirm the prefix is specified correctly')
    
    # Determine the input files from the prefix
    ped_prefix_filenames = glob.glob(ped_prefix + '*')

    # Check if files were identified, if not return error message
    if not ped_prefix_filenames:
        raise IOError('Unable to assign input files from PED prefix. Please confirm the prefix is specified correctly')
    
    # Check if expected files are found
    for ped_prefix_filename in ped_prefix_filenames:

        # Check for PED and MAP files
        if ped_prefix_filename.endswith('.ped'):
            ped_filename = ped_prefix_filename
        elif ped_prefix_filename.endswith('.map'):
            map_filename = ped_prefix_filename

    # Check that input files included a ped file
    if not ped_filename:
        # Return error message if no ped input was found
        raise IOError('Unable to assign ped file. Please confirm the prefix and/or command is specified correctly')

    if not map_filename:
        # Return error message if no map input was found
        raise IOError('Unable to assign map file. Please confirm the file is named correctly')

    # Return the ped associated args
    return ['--file', ped_filename[:-4]]

def assign_bed_from_files (bed_filename = None, bim_filename = None, fam_filename = None, **kwargs):

    # Check if a bed file is assigned
    if not bed_filename:
        raise IOError('Unable to assign binary-ped file. Please confirm the file is named correctly')

    # Check if the bim and fam files are not assigned
    if not bim_filename and not fam_filename:
        raise IOError('Unable to assign the bim and fam files. Please confirm the files (i.e. --bim, --fam) are assigned')

    # Check if the bim is not assigned
    if not bim_filename:
        raise IOError('Unable to assign bim file. Please confirm the bim file (i.e. --bim) is assigned')

    # Check if the fam file is not assigned
    if not fam_filename:
        raise IOError('Unable to assign fam file. Please confirm the fam file (i.e. --fam) is assigned')

    # Return the bed associated args
    return ['--bed', bed_filename, '--bim', bim_filename, '--fam', fam_filename]

def assign_bed_from_prefix (bed_prefix = None, **kwargs):

    # Check if the a prefix was assigned
    if not bed_prefix:
        raise IOError('No Binary-PED prefix specified. Please confirm the prefix is specified correctly')
    
    # Determine the input files from the prefix
    bed_prefix_filenames = glob.glob(bed_prefix + '*')

    # Check if files were identified, if not return error message
    if not bed_prefix_filenames:
        raise IOError('Unable to assign input files from Binary-PED prefix. Please confirm the prefix is specified correctly')
    
    # Check if expected files are found
    for bed_prefix_filename in bed_prefix_filenames:

        # Check for BED and associated files
        if bed_prefix_filename.endswith('.bed'):
            bed_filename = bed_prefix_filename
        elif bed_prefix_filename.endswith('.bim'):
            bim_filename = bed_prefix_filename
        elif bed_prefix_filename.endswith('.fam'):
            fam_filename = bed_prefix_filename

    # Check that input files included a bed file
    if not bed_filename:
        # Return error message if no ped/bed input was found
        raise IOError('Unable to assign bed file. Please confirm the prefix and/or command is specified correctly')

    # Check that input files included a bed file
    if not bim_filename:
        # Return error message if no bim input was found
        raise IOError('Unable to assign bim file. Please confirm the file is named correctly')

    # Check that input files included a bed file
    if not fam_filename:
        # Return error message if no fam input was found
        raise IOError('Unable to assign fam file. Please confirm the file is named correctly')

    # Return the binary-ped args
    return ['--bfile', bed_filename[:-4]]
    
def convert_vcf_to_plink (vcf_filename, vcf_fid, out_prefix, out_format, threads = 1, overwrite = False):

    logging.info('Beginning VCF conversion')

    # List of arguments for bed converions
    convert_vcf_args = []

    # Check if a specific number of threads have been assigned
    if threads:

        convert_vcf_args.extend(['--threads', threads])

    # Assign the vcf file format
    vcfname_format = checkFormat(vcf_filename)

    # Check if a family ID was assigned for the vcf file
    if vcf_fid:

        # Assign the family id
        convert_vcf_args.extend(['--const-fid', vcf_fid])

    # If no family ID was assigned, use double IDs
    else:

        convert_vcf_args.append('--double-id')

    convert_vcf_args.append('--allow-extra-chr')

    # Assign the associated input command, or return an error.
    if vcfname_format == 'vcf' or vcfname_format == 'bgzip':

        # Add the bed associated commands
        convert_vcf_args.extend(['--vcf', vcf_filename])

    elif vcfname_format == 'bcf':

        # Add the bed associated commands
        convert_vcf_args.extend(['--bcf', vcf_filename])

    else:
        raise Exception('Unknown VCF file format')

    # Assign the output arguments
    vcf_output_args = assign_plink_output_args(out_prefix, out_format, overwrite)

    # Add the output args to the ped call
    convert_vcf_args.extend(vcf_output_args)

    # Call plink with the selected arguments
    call_plink(convert_vcf_args, out_prefix, out_format)

    logging.info('Finished conversion')

def convert_ped (ped_filename = None, map_filename = None, ped_prefix = None, out_prefix = None, out_format = None, threads = 1, overwrite = False, **kwargs):
    
    logging.info('Beginning PED conversion')

    # List of arguments for bed converions
    convert_ped_args = []

    # Check if a specific number of threads have been assigned
    if threads:

        convert_ped_args.extend(['--threads', threads])

    # Create blank list to hold ped input arguments
    ped_prefix_args = []

    # Check if the a prefix was assigned
    if ped_prefix:
    
        # Assign bed input arguments from a prefix
        ped_prefix_args = assign_ped_from_prefix(ped_prefix)

    # Check if a bed file is assigned
    elif ped_filename:

        # Assign bed input arguments from files
        ped_prefix_args = assign_ped_from_files(ped_filename, map_filename)

    # Add the ped input arguments
    convert_ped_args.extend(ped_prefix_args)

    # Assign the output arguments
    ped_output_args = assign_plink_output_args(out_prefix, out_format, overwrite)

    # Add the output args to the ped call
    convert_ped_args.extend(ped_output_args)

    # Call plink with the selected arguments
    call_plink(convert_ped_args, out_prefix, out_format)

    logging.info('Finished conversion')

def convert_bed (bed_filename = None, bim_filename = None, fam_filename = None, bed_prefix = None, out_prefix = None, out_format = None, threads = 1, overwrite = False, **kwargs):
        
    logging.info('Beginning Binary-PED (i.e. BED) conversion')

    # List of arguments for bed converions
    convert_bed_args = []

    # Check if a specific number of threads have been assigned
    if threads:

        convert_bed_args.extend(['--threads', threads])

    # Create blank list to hold bed input arguments
    bed_prefix_args = []

    # Check if the a prefix was assigned
    if bed_prefix:
    
        # Assign bed input arguments from a prefix
        bed_prefix_args = assign_bed_from_prefix(bed_prefix)

    # Check if a bed file is assigned
    elif bed_filename:

        # Assign bed input arguments from files
        bed_prefix_args = assign_bed_from_files(bed_filename, bim_filename, fam_filename)

    # Confirm input arguments were assigned
    if not bed_prefix_args:
        raise Exception('Unable to assign Binary-PED input arguments. Please confirm the arguments are specified correctly')

    # Add the bed input arguments
    convert_bed_args.extend(bed_prefix_args)

    # Assign the output arguments
    bed_output_args = assign_plink_output_args(out_prefix, out_format, overwrite)

    # Add the output args to the ped call
    convert_bed_args.extend(bed_output_args)

    # Call plink with the selected arguments
    call_plink(convert_bed_args, out_prefix, out_format)

    logging.info('Finished conversion')

def convert_haps_to_vcf (haps_prefix, output_format, output_prefix = ''):

    # Check that input files included a haps file
    if not os.path.isfile(haps_prefix + '.haps'):
        # Return error message if no haps input was found
        raise IOError('Unable to assign haps file. Please confirm the prefix and/or command is specified correctly')

    # Check that input files included a sample file
    if not os.path.isfile(haps_prefix + '.sample'):
        # Return error message if no sample input was found
        raise IOError('Unable to assign sample file. Please confirm the prefix and/or command is specified correctly')

    haps_input_args = ['--haps', haps_prefix + '.haps', 'ref-first', '--sample', haps_prefix + '.sample']

    # If no output_prefix is assigned, use haps_prefix
    if not output_prefix:
        output_prefix = haps_prefix

    plink_delim = assign_delim_from_ids(haps_prefix + '.sample')

    # Assign general command line arguments
    haps_output_args = ['--recode', 'vcf-iid', 'id-delim=' + plink_delim, '--out', output_prefix]

    # Check if a compressed file should be created
    if output_format in ['vcf.gz', 'bcf']:

        # Insert the compression argument
        haps_output_args.insert(2, 'bgz')

    # Call plink2
    standard_plink2_call(haps_input_args + haps_output_args)

    # Convert VCFGZ to BCF, as PLINK cannot directly create a BCF
    if output_format == 'bcf':

        # Convert to BCF
        convert_vcf(output_prefix + '.vcf.gz', output_prefix, output_format, overwrite = True)

def check_plink_for_errors (plink_stderr):
    '''
        Checks the plink stderr for errors

        Parameters
        ----------
        plink_stderr : str
            plink stderr

        Raises
        ------
        IOError
            If plink stderr returns an error
    '''

    # Print output if error found. Build up as errors are discovered
    if plink_stderr:
        raise Exception(plink_stderr)

def standard_plink2_call (plink2_call_args):
    '''
        Standard call of plink2

        The function calls plink2. Returns the stderr of plink to create a log
        file of the call.

        Parameters
        ----------
        plink2_call_args : list
            plink2 arguments

        Raises
        ------
        Exception
            If plink2 stderr returns an error
    '''


    # plink subprocess call
    plink2_call = subprocess.Popen(['plink2'] + list(map(str, plink2_call_args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for plink to finish
    plink2_out, plink2_err = plink2_call.communicate()

    # Check if code is running in python 3
    if sys.version_info[0] == 3:
        # Convert bytes to string
        plink2_out = plink2_out.decode()
        plink2_err = plink2_err.decode()

    logging.info('plink2 call complete')

    # Check that the log file was created correctly
    check_plink_for_errors(plink2_err)

def standard_plink_call (plink_call_args):
    '''
        Standard call of plink

        The function calls plink. Returns the stderr of plink to create a log
        file of the call.

        Parameters
        ----------
        plink_call_args : list
            plink arguments

        Raises
        ------
        Exception
            If plink stderr returns an error
    '''

    # plink subprocess call
    plink_call = subprocess.Popen(['plink'] + list(map(str, plink_call_args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for plink to finish
    plink_out, plink_err = plink_call.communicate()

    # Check if code is running in python 3
    if sys.version_info[0] == 3:
        # Convert bytes to string
        plink_out = plink_out.decode()
        plink_err = plink_err.decode()

    logging.info('plink call complete')

    # Check that the log file was created correctly
    check_plink_for_errors(plink_err)

def call_plink (plink_call_args, output_prefix = None, output_format = None):
    '''
        Determines which version of plink (plink1.9 vs. plink2a) to call

        The function is required for the plink wrapper to determine the needed
        plink version and also automates conversion to BCF, which both versions
        of plink do not support.

        Parameters
        ----------
        plink_call_args : list
            plink arguments
        output_prefix : str
            Output prefix for non-plink conversions
        output_format : str
            Output format for non-plink conversions

    '''

    # Check if the call requries plink2 to operate. This function should be
    # removed once plink2 is out of alpha
    if '--haps' in plink_call_args:

        # Convert vcf id system for plink 1.9 to plink 2
        if 'vcf-iid' in plink_call_args:
            format_index = plink_call_args.index('vcf-iid')
            plink_call_args[format_index:format_index + 1] = ['vcf', 'id-paste=fid']

        # Call the plink2 subprocess function
        standard_plink2_call(plink_call_args)

    # Call plink1.9
    else:

        # Call the plink subprocess function
        standard_plink_call(plink_call_args)

    # Convert VCFGZ to BCF, as PLINK cannot directly create a BCF
    if output_format == 'bcf':

        # Convert to BCF
        convert_vcf(output_prefix + '.vcf.gz', output_prefix, output_format)