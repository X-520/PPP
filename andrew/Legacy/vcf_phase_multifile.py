import os
import sys
import subprocess
import shutil
import argparse
import glob
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.pardir, 'jared')))

import vcf_reader_func
from logging_module import initLogger

def phase_argument_parser(passed_arguments):
    '''Phase Argument Parser - Assigns arguments for vcftools from command line.
    Depending on the argument in question, a default value may be specified'''

    def parser_confirm_and_append_file ():
        '''Custom action to confirm file exists'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, value, option_string=None):
                if not os.path.isfile(value):
                    raise IOError # File not found
                # Check if the argument has been set
                if getattr(args, self.dest):
                    # Append the argument with the file
                    getattr(args, self.dest).append(value)

                else:
                    # Set the argument with the file (as list)
                    setattr(args, self.dest, [value])

        return customAction

    def metavar_list (var_list):
        '''Create a formmated metavar list for the help output'''
        return '{' + ', '.join(var_list) + '}'

    phase_parser = argparse.ArgumentParser()

    # Input arguments.
    phase_parser.add_argument("--vcf", help = "Input VCF filename", type = str, action = parser_confirm_and_append_file())

    phasing_list = ['beagle', 'shapeit']
    phasing_default = 'beagle'
    phase_parser.add_argument('--phase-algorithm', metavar = metavar_list(phasing_list), help = 'Specifies the phase algorithm to be used', type = str, choices = phasing_list, default = phasing_default)

    # General output
    phase_parser.add_argument('--out-prefix', help = 'Defines the output prefix (used by phasing algorithms)', default = 'out')

    # Multiple vcf output options
    phase_parser.add_argument('--out-dir', help = 'Specifies the output directory when processing multiple files', type = str, default = 'Phased_Files')
    phase_parser.add_argument('--log-dir', help = 'Specifies the log directory when processing multiple files', type = str, default = 'Phased_Logs')

    # Single vcf output options
    phase_parser.add_argument('--out', help = 'Defines the output filename. Cannot be used when processing multiple files')
    phase_parser.add_argument('--log', help = 'Defines the log filename. Cannot be used when processing multiple files')

    if passed_arguments:
        return phase_parser.parse_args(passed_arguments)
    else:
        return phase_parser.parse_args()

def logArgs(args, pipeline_function):
    '''Logs arguments from argparse system. May be replaced with a general function in logging_module'''
    logging.info('Arguments for %s:' % pipeline_function)
    for k in vars(args):
        logging.info('Arguments %s: %s' % (k, vars(args)[k]))

def assign_vcf_extension (filename):
    # Checks if the file is unzipped, bgzipped, or gzipped
    vcfname_format = vcf_reader_func.checkFormat(filename)

    if vcfname_format == 'nozip':
        return '.vcf'
    elif vcfname_format == 'gzip' or vcfname_format == 'bgzip':
        return '.vcf.gz'
    else:
        sys.exit('Unknown file format')

def check_beagle_for_errors (beagle_stdout):
    '''
        Checks the beagle stdout for errors

        Parameters
        ----------
        beagle_stdout : str
            beagle stdout

        Raises
        ------
        IOError
            If beagle stdout returns an error
    '''

    # Returns True if the job completed without error
    if 'End time:' in str(beagle_stdout) and 'finished'  in str(beagle_stdout):
        pass

    # Print output for beagle if error is detected
    elif 'ERROR:' in str(beagle_stdout):
        # Splits log into list of lines
        beagle_stdout_lines = beagle_stdout.splitlines()
        # Prints the error(s)
        logging.error('\n'.join((output_line for output_line in beagle_stdout_lines if output_line.startswith('ERROR:'))))
        raise Exception('\n'.join((output_line for output_line in beagle_stdout_lines if output_line.startswith('ERROR:'))))

    # Print output if not completed and no error found. Unlikely to be used, but included.
    else:
        logging.error(beagle_stdout)
        raise Exception(beagle_stdout)

def check_shapeit_for_errors (shapeit_stdout):
    '''
        Checks the shapeit stdout for errors

        Parameters
        ----------
        shapeit_stdout : str
            shapeit stdout

        Raises
        ------
        IOError
            If shapeit stdout returns an error
    '''

    # Returns True if the job completed without error
    if 'Running time:' in str(shapeit_stdout):
        pass

    # Print output if not completed and no error found. Unlikely to be used, but included.
    else:
        logging.error(shapeit_stdout)
        raise Exception(shapeit_stdout)

def combine_shapeit_logs (shapeit_logs, new_log_filename):
    # Combine log files
    with open(new_log_filename, 'wb') as out_file:
        for shapeit_log in shapeit_logs:
            if not os.path.isfile(shapeit_log):
                raise IOError # File not found
            with open(shapeit_log, 'rb') as in_file:
                shutil.copyfileobj(in_file, out_file)
    # Remove old log files
    for shapeit_log in shapeit_logs:
        os.remove(shapeit_log)

def phase_file (phase_args):

    # Assign file extension for VCF input file
    vcfname_ext = assign_vcf_extension(phase_args.vcf)

    logging.info('Input file assigned')

    # Used to confirm if the VCF input was renamed
    vcfname_renamed = False

    # Confirm input has correct file extension
    if vcfname_ext not in phase_args.vcf:
        vcfname_renamed = True
        os.rename(phase_args.vcf, phase_args.vcf + vcfname_ext)
        phase_args.vcf += vcfname_ext

    if phase_args.phase_algorithm == 'beagle':
        # Assign the algorithm
        algorithm_call_args = ['java', '-jar', '/home/aewebb/Repositories/PPP/andrew/bin/beagle.jar']

        # Assigns the arguments for phasing
        phase_call_args = ['gt=' + phase_args.vcf, 'out=' + phase_args.out_prefix]

        logging.info('beagle phasing parameters assigned')

        # Phasing subprocess call
        phase_call = subprocess.Popen(algorithm_call_args + phase_call_args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        phase_out, phase_err = phase_call.communicate()

        # Check beagle call for errors
        check_beagle_for_errors(phase_out)

        logging.info('beagle phasing complete')

        # Rename output to phase_args.out, if specified
        if phase_args.out:
            shutil.move(phase_args.out_prefix + vcfname_ext, phase_args.out)

        # Rename log to phase_args.log, if specified
        if phase_args.log:
            shutil.move(phase_args.out_prefix + '.log', phase_args.log)
        # Rename log using phase_args.out, if specified
        elif phase_args.out:
            shutil.move(phase_args.out_prefix + '.log', phase_args.out + '.log')
        # Rename log using phase_args.out_prefix
        else:
            shutil.move(phase_args.out_prefix + '.log', phase_args.out_prefix + vcfname_ext + '.log')

        logging.info('beagle log file created')

    elif phase_args.phase_algorithm == 'shapeit':
        # Assign the algorithm
        algorithm_call_args = ['shapeit']

        # Assigns the arguments for phasing
        phase_call_args = ['--input-vcf', phase_args.vcf, '-O', phase_args.out_prefix, '-L', phase_args.out_prefix + '.p.log']

        logging.info('shapeit phasing parameters assigned')

        # Phasing subprocess call
        phase_call = subprocess.Popen(algorithm_call_args + phase_call_args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        phase_out, phase_err = phase_call.communicate()

        # Check shapeit call for errors
        check_shapeit_for_errors(phase_out)

        logging.info('shapeit phasing complete (non-VCF format)')

        # Assigns the arguments for converting the phased output into a vcf file
        convert_call = ['-convert', '--input-haps', phase_args.out_prefix, '--output-vcf', phase_args.out_prefix + vcfname_ext, '-L', phase_args.out_prefix + '.c.log']

        logging.info('shapeit conversion parameter assigned')

        # Convert subprocess call
        convert_call = subprocess.Popen(algorithm_call_args + convert_call, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        convert_out, convert_err = convert_call.communicate()

        # Check shapeit call for errors
        check_shapeit_for_errors(convert_out)

        logging.info('shapeit conversion to VCF complete')

        # Rename output to phase_args.out, if specified
        if phase_args.out:
            shutil.move(phase_args.out_prefix + vcfname_ext, phase_args.out)

        # Rename log to phase_args.log, if specified
        if phase_args.log:
            combine_shapeit_logs([phase_args.out_prefix + '.p.log', phase_args.out_prefix + '.c.log'],  phase_args.log)
        # Rename log using phase_args.out, if specified
        elif phase_args.out:
            combine_shapeit_logs([phase_args.out_prefix + '.p.log', phase_args.out_prefix + '.c.log'],  phase_args.out + '.log')
        # Rename log using phase_args.out_prefix
        else:
            combine_shapeit_logs([phase_args.out_prefix + '.p.log', phase_args.out_prefix + '.c.log'],  phase_args.out_prefix + vcfname_ext + '.log')

        logging.info('shapeit log file created')

        # Add options for not removing
        os.remove('out.haps')
        os.remove('out.sample')
        os.remove('out.p.ind.mm')
        os.remove('out.p.snp.mm')

        logging.info('shapeit intermediate file removed')

    # Reverts the VCF input file
    if vcfname_renamed:
        os.rename(phase_args.vcf, phase_args.vcf[:-len(vcfname_ext)])

def run (passed_arguments = []):
    '''
        Phaser for VCF files.

        Automates the phasing process for a specified VCF file. The function
        allows users to select between multiple phasing algorithms: beagle
        (default) and shapit.

        Parameters
        ----------
        VCF_Input : str
            Specifies the input VCF filename
        --phase-algorithm : str
            Specifies the algorithm to be used. Choices: beagle (default) and
            shapit
        --out : str
            Specifies the output filename
        Returns
        -------
        output : file
            Phased VCF file

        Raises
        ------
        IOError
            Input VCF file does not exist
        IOError
            Output file already exists

    '''

    # Grab VCF arguments from command line
    phase_args = phase_argument_parser(passed_arguments)

    # Adds the arguments (i.e. parameters) to the log file
    logArgs(phase_args, 'vcf_phase')

    # Confirm that at least once vcf file was assigned as input
    if not phase_args.vcf:
        logging.error('No VCF file assigned')
        raise IOError('No VCF file assigned')

    if len(phase_args.vcf) == 1:
        phase_args.vcf = phase_args.vcf[0]
        phase_file(phase_args)

    # Confirm that the options specified are compatible with multiple input files
    elif len(phase_args.vcf) > 1:
        # Check if the out argument has been specified
        if phase_args.out:
            logging.error('The --out option cannot be used when processing multiple files')
            raise IOError('The --out option cannot be used when processing multiple files')
        # Check if the log argument has been specified
        if phase_args.log:
            logging.error('The --log option cannot be used when processing multiple files')
            raise IOError('The --log option cannot be used when processing multiple files')

        # Create the vcf/bcf output directory
        if not os.path.exists(phase_args.out_dir):
            os.makedirs(phase_args.out_dir)

        # Create the log output directory
        if not os.path.exists(phase_args.log_dir):
            os.makedirs(phase_args.log_dir)

        # Store the input vcf filepaths within a list
        vcfs_to_process = phase_args.vcf

        # Loop the input vcf filepaths
        for current_vcf in vcfs_to_process:
            # Assign the input
            phase_args.vcf = current_vcf

            # Assign the vcf basename
            out_basename = os.path.basename(current_vcf)
            # Remove file extension
            out_basename_wo_ext = out_basename.split(os.extsep)[0]
            # Assign the vcf output filepath
            out_filepath = os.path.join(phase_args.out_dir, out_basename_wo_ext + '.vcf.gz')
            # Assign the input
            phase_args.out = out_filepath

            # Assign the vcf basename
            log_basename = out_basename_wo_ext + '.log'
            # Assign the vcf output filepath
            log_filepath = os.path.join(phase_args.log_dir, log_basename)
            # Assign the log
            phase_args.log = log_filepath

            # Process the file
            phase_file(phase_args)


if __name__ == "__main__":
    initLogger()
    run()
