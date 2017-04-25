import os
import sys
import subprocess
import argparse
import logging

from vcftools import *

# Insert Jared's directory path, required for calling Jared's functions. Change when directory structure changes.
sys.path.insert(0, os.path.abspath(os.path.join(os.pardir,'jared')))

#from logging_module import initLogger

def vcf_calc_parser(passed_arguments):
    '''VCF Argument Parser'''
    
    def parser_confirm_file ():
        '''Custom action to confirm file exists'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, value, option_string=None):
                if not os.path.isfile(value):
                    raise IOError # File not found
                setattr(args, self.dest, value)
        return customAction
    
    def parser_confirm_no_file ():
        '''Custom action to confirm file does not exist'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, value, option_string=None):
                if os.path.isfile(value):
                    raise IOError # File found
                setattr(args, self.dest, value)
        return customAction
    
    def parser_confirm_files ():
        '''Custom action to confirm multiple file exists'''
        class customAction(argparse.Action):
            def __call__(self, parser, args, value, option_string=None):
                if not os.path.isfile(value):
                    raise IOError # File not found
                getattr(args, self.dest).append(value)                
        return customAction
        
    vcf_parser = argparse.ArgumentParser(formatter_class = argparse.ArgumentDefaultsHelpFormatter)
    
    # Input arguments. 
    vcf_parser.add_argument("vcfname", metavar='VCF_Input', help = "Input VCF filename", type = str, action = parser_confirm_file())
    
    # Other file arguments. Expand as needed
    vcf_parser.add_argument('--out', help = 'Specifies the output filename', type = str,  default = 'out', action = parser_confirm_no_file())
    vcf_parser.add_argument('--pop-file', help = 'Defines the population files for calculating specific statistics', type = str, action='append')

    # Statistic based arguments.
    statistic_list = ['windowed-weir-fst', 'TajimaD', 'pi', 'freq', 'het']
    statistic_default = 'windowed-weir-fst'
    
    vcf_parser.add_argument('--calc-statistic', metavar = '{' + ', '.join(statistic_list) + '}', help = 'Specifies the statistic to calculate', type=str, choices = statistic_list, default = statistic_default)
    
    # Statistic window options
    vcf_parser.add_argument('--statistic-window-size', help = 'Specifies the size of window calculations', type = int, default = 10000)
    vcf_parser.add_argument('--statistic-window-step', help = 'Specifies step size between windows', type = int, default = 20000)

          
    if passed_arguments:
        return vcf_parser.parse_args(passed_arguments)
    else:
        return vcf_parser.parse_args()

def run (passed_arguments = []):
    '''
    PPP script for automating statistic calculations using VCFTools .
    
    The VCFTools wrapper was designed to simplify the use of VCFTools within the PPP.
    The function is capable of operating within the pipeline (i.e. imported & called)
    or individually. Currently, the functions uses argparse to correctly assign the
    the parameters to VCFTools.
        
    '''
    
    # Grab VCF arguments from command line
    vcf_args = vcf_calc_parser(passed_arguments)
    
    # Argument container for vcftools
    vcftools_call_args = [['--out', vcf_args.out]]
    
    if vcf_args.calc_statistic == 'windowed-weir-fst':
        # Confirms that at least two population files have been specified
        if not vcf_args.pop_file or len(vcf_args.pop_file) < 2:
            sys.exit('Two or more population files requried. Please assign using --pop-file')
        
        # Assigns specific vcftools arguments for calculating fst
        vcftools_pop_args = [population_args for population_file in vcf_args.pop_file for population_args in ['--weir-fst-pop', population_file]]
        vcftools_window_args = ['--fst-window-size', vcf_args.statistic_window_size, '--fst-window-step', vcf_args.statistic_window_step]
        
        # Assigns all the vcftools arguments for calculating fst
        vcftools_call_args = vcftools_pop_args + vcftools_window_args
        
        # Assigns the suffix for the vcftools log file
        vcftools_log_suffix = '.windowed.weir.fst'
        
    elif vcf_args.calc_statistic == 'TajimaD':
        
        # Assigns all the vcftools arguments for calculating TajimaD
        vcftools_call_args = ['--TajimaD', vcf_args.statistic_window_size]
        
        # Assigns the suffix for the vcftools log file
        vcftools_log_suffix = '.Tajima.D'
        
    elif vcf_args.calc_statistic == 'pi':
        
        # Assigns all the vcftools arguments for calculating pi
        vcftools_call_args = ['--window-pi', vcf_args.statistic_window_size, '--window-pi-step', vcf_args.statistic_window_step]
        
        # Assigns the suffix for the vcftools log file
        vcftools_log_suffix = '.windowed.pi'
                
    elif vcf_args.calc_statistic == 'freq':
        
        # Assigns all the vcftools arguments for the allele frequency
        vcftools_call_args = ['--freq']
        
        # Assigns the suffix for the vcftools log file
        vcftools_log_suffix = '.frq'
        
    elif vcf_args.calc_statistic == 'het':
        
        # Assigns all the vcftools arguments for calculating heterozygosity
        vcftools_call_args = ['--het']
        
        # Assigns the suffix for the vcftools log file
        vcftools_log_suffix = '.het'
       
    # Assigns the file argument for vcftools
    vcfname_arg = assign_vcftools_input_arg(vcf_args.vcfname)
    
    # vcftools subprocess call
    vcftools_call = subprocess.Popen(['vcftools'] + vcfname_arg + list(map(str, vcftools_call_args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    vcftools_out, vcftools_err = vcftools_call.communicate()

    # Check that the log file was created correctly, get the suffix for the log file, and create the file
    if check_vcftools_for_errors(vcftools_err):
        produce_vcftools_log(vcftools_err, vcf_args.out, vcftools_log_suffix)
        
if __name__ == "__main__":
    #initLogger()
    run()