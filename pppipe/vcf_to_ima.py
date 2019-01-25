import sys
import pysam
import argparse
import os
import logging
from random import sample
from collections import OrderedDict

import pppipe.vcf_reader_func as vf
from pppipe.logging_module import initLogger, logArgs
from pppipe.gene_region import Region, RegionList
from pppipe.parse_functions import defaultsDictForFunction, getConfigFilename, makeRequiredList, getArgsWithConfig
from pppipe.model import Model, read_model_file
#from tabix_wrapper import prepVcf

#Input: VCF file, reference sequence, region list (possibly .bed file)
#Output: Sequences with reference genome overlayed with VCF SNP calls

#sys.path.insert(0,os.path.abspath(os.path.join(os.pardir, 'andrew')))


class locus():
    #Name, pops, store for seqs, length, mut model, scalar, mutrate
    def __init__(self, gener, rec_list, popmodel, args):
        if args.inhet_sc is None:
            if gener.chrom in ['X','chrX']:
                self.inhet_sc = 0.75
            elif gener.chrom in ['Y','chrY','MT','chrMT']:
                self.inhet_sc = 0.25
            else:
                self.inhet_sc = 1
        else:
            self.inhet_sc = args.inhet_sc
        self.name = gener.chrom+':'+str(gener.start)+':'+str(gener.end)
        self.gene_len = gener.end - gener.start
        for rec in rec_list:
            self.gene_len += (getMaxAlleleLength(rec.alleles) - len(rec.ref))
        self.popmodel = popmodel
        self.popkeys = []
        self.seqs = {}
        for p in popmodel.pop_list:
            self.popkeys.append(p)
            self.seqs[p] = []
        self.mut_model = 'I'
        #if args.mut_model is not None:
        #    if args.mut_model not in ['I','H','S','J','IS']:
        #        raise Exception("%s is an invalid mutation model (must select from I,H,S,J,IS)" % (args.mut_model))
        #    self.mut_model = args.mut_model
        if args.refname is not None and args.printseq:
            self.seq_len = self.gene_len
        else:
            self.seq_len = len(rec_list)
        self.mutrate = self.gene_len * args.mutrate

    def addSeq(self,seq,pop):
        try:
            self.seqs[pop].append(seq)
        except IndexError:
            raise Exception("Pop %s is not in pop list" % pop)

    def printToFile(self, outf = sys.stdout):
        out_str = ''
        out_str += (self.name)+' '
        for p in self.popkeys:
            out_str += (str(len(self.seqs[p]))+' ')
        out_str += str(self.seq_len)+' '
        out_str += self.mut_model + ' '
        out_str += str(self.inhet_sc)+' '
        out_str += str("%.14f" % (self.mutrate))+'\n'
        outf.write(out_str)
        for p in self.popkeys:
            for seq in self.seqs[p]:
                outf.write(seq+'\n')

class outputBuffer():

    def __init__(self, popmodel, outfile=sys.stdout):
        self.header = None
        self.hold = True
        self.outfile = outfile
        self.popmodel = popmodel
        self.poptree = None
        self.loci = []

    def createHeader(self):
        self.header = {}
        self.header['title'] = 'Test IMa input'
        self.header['pops'] = [p for p in self.popmodel.pop_list]

    def writeHeader(self):
        self.outfile.write(self.header['title']+'\n')
        self.outfile.write(str(len(self.header['pops']))+'\n')
        self.outfile.write(' '.join(self.header['pops'])+'\n')
        if self.poptree is not None:
            self.outfile.write(self.poptree+'\n')
        self.outfile.write(str(len(self.loci)+'\n'))



def createParser():
    parser = argparse.ArgumentParser(description=("Generates an IMa input "
                                     "file from a VCF file, a reference"
                                     " genome, a list of gene regions, "
                                     "and a population info file."),
                                     fromfile_prefix_chars="@")
    parser.add_argument("--vcf", dest="vcfname", help="Input VCF filename")
    parser.add_argument("--vcfs", dest="vcflist", nargs="+")
    parser.add_argument("--ref", dest="refname", help="Reference FASTA file")
    parser.add_argument("--bed", dest="genename",
                        help="Name of gene region file")
    parser.add_argument("--pop", dest="popname", help=("Filename of pop "
                        "model file"))
    parser.add_argument("--zero-ho", dest="zeroho", action="store_true",
                        help="Region coordinates are zero-based, half-open")
    parser.add_argument("--zero-closed", dest="zeroclosed", action="store_true")
    parser.add_argument("--keep-indels", dest="indel_flag", action="store_true",
                        help="Include indels when reporting sequences")
    parser.add_argument("--remove-multiallele",dest="remove_multiallele",
                        action="store_true", help=("Remove sites with more "
                        "than two alleles"))
    #parser.add_argument("--remove-missing", dest="remove_missing", default=-1,
    #                   help=("Will filter out site if more than the given "
    #                    "number of individuals (not genotypes) are missing "
    #                    "data. 0 removes sites with any missing data, -1 "
    #                    "(default) removes nothing"),type=int)
    parser.add_argument("--drop-missing-sites",dest="remove_missing",action="store_const",const=0,default=-1,help=("Will remove sites with missing data instead of throwing error"))
    parser.add_argument("--parsecpg",dest="parsecpg",action="store_true")
    parser.add_argument("--noseq",dest="printseq",action="store_false",
                        help=("Will only print variants when reference is "
                        "provided. Used so CpG filtering can be done if "
                        "invariant sites aren't desired in output"))
    parser.add_argument("--trim-to-ref-length", dest="trim_seq",
                        action="store_true",
                        help=("Trims sequences if indels cause them to be "
                        "longer than reference"))
    parser.add_argument("--output", dest="output_name", default="input.ima.u",
                        help= ("Optional name for output other than default"))
    parser.add_argument("--gene-col", dest="gene_col", help= (
                        "Comma-separated list of columns for gene region "
                        " data, format is start/end if no chromosome "
                        " data, start/end/chrom if so"))
    parser.add_argument("--compress-vcf", dest="compress_flag",
                        action="store_true", help=("If input VCF is not "
                        "compressed, will compress and use zip search"))
    parser.add_argument("--conf", dest="config_name", help= ("Name of "
                        "file with configuration options"))
    parser.add_argument("--no-ref-check", dest="ref_check",
                        action="store_false", help=("Prevents exception "
                        "generated by mismatched reference alleles from "
                        "VCF file compared to reference"))
    parser.add_argument("--poptag",dest="poptag",help=("If model file has "
                        "multiple models, use model with this name"))
    parser.add_argument("--mutrate",dest="mutrate",type=float,default=1e-9,
                        help="Mutation rate per base pair (default is 1e-9)")
    parser.add_argument("--inheritance-scalar",dest="inhet_sc",type=float,
                        default=None)
    parser.add_argument("--fasta",dest="fasta",action="store_true")
    parser.add_argument("--multi-out",dest="multi_out",type=str)
    parser.add_argument("--drop-missing-inds",dest="drop_inds",action="store_true",
                        help="Drop individuals from loci if they are missing any data")
    return parser


def checkArgs(args):
    if args.vcfname is None and args.vcflist is None:
        raise Exception("Must provide at least one VCF file to either --vcf or --vcfs")
    if args.vcfname is not None and args.vcflist is not None:
        raise Exception("Cannot use both arguments --vcf and --vcfs")
    if args.vcfname is not None and args.genename is None:
        raise Exception("If using --vcf, must provide a BED file with --bed")
    if args.refname is None and args.parsecpg:
        raise Exception("CpG parsing requires reference genome (--ref)")
    if args.popname is None and not args.fasta:
        raise Exception("IMa file requires model input with --pop")


def validateFiles(args):
    """Validates that files provided to args all exist on users system"""
    for var in ['vcfname', 'refname', 'genename','popname']:
        f = vars(args)[var]
        if f is not None and not os.path.exists(f):
            raise ValueError('Filepath for %s not found at %s' %
                            (var, f))
    if args.vcflist is not None:
        for f in args.vcflist:
            if not os.path.exists(f):
                raise ValueError(('File not found at %s') % f)


def getMaxAlleleLength(alleles):
    """If an indel, returns length of longest allele (returns 1 for snp)"""
    return max([len(r) for r in alleles])


def checkRefAlign(vcf_recs, fasta_ref, chrom, ref_check):
    """Compares sequence from record to reference FASTA sequence"""
    for vcf_r in vcf_recs:
        vcf_seq = vcf_r.ref
        pos = vcf_r.pos-1
        try:
            fasta_seq = fasta_ref.fetch(vcf_r.chrom, pos, pos+len(vcf_seq))
        except KeyError:
            fasta_seq = fasta_ref.fetch(vf.flipChrom(vcf_r.chrom),pos,pos+len(vcf_seq))
        if vcf_seq.upper() != fasta_seq.upper():
            if ref_check:
                raise Exception(("VCF bases and reference bases do not match."
                        "\nVCF reference: %s\nFASTA reference: "
                        "%s\nPosition: %s") % (vcf_seq, fasta_seq, str(pos)))
            else:
                logging.warning("Bases at position %s do not match" %
                            str(pos))
                break


def generateSequence(rec_list, ref_seq, region, chrom, indiv, idx, args):
    """Fetches variant sites from a given region, then outputs sequences
    from each individual with their correct variants. Will print sequence
    up to the variant site, then print correct variant. After last site,
    will output the rest of the reference sequence."""
    #var_sites = vcf_reader.fetch(chrom,region.start,region.end)
    fl = 0
    seq = ''
    prev_offset = 0

    for vcf_record in rec_list:
        issnp = vf.checkRecordIsSnp(vcf_record)
        if not args.indel_flag and not issnp:
            continue

        #If reference included, add all bases between last and current variant
        pos_offset = vcf_record.pos - 1 - region.start
        if ref_seq is not None:
            for i in range(prev_offset, pos_offset):
                seq += ref_seq[i]

        allele = vcf_record.samples[indiv].alleles[idx]
        if allele is None:
            raise Exception(("Individual %d at position %d is missing "
            "data") % (vcf_record.pos,indiv))
        if issnp:
            #Place allele, move reference offset
            seq += vcf_record.samples[indiv].alleles[idx]
            prev_offset = pos_offset+1
        else:
            #Find longest allele, pad others to its length
            #Offset by length of reference allele
            max_indel = getMaxAlleleLength(vcf_record.alleles)
            allele = vcf_record.samples[indiv].alleles[idx]
            if allele is None:
                allele = 'N'
            for i in range(len(allele), max_indel):
                allele += '_'
            seq += allele
            indel_offset = len(vcf_record.ref)
            prev_offset = pos_offset+indel_offset
    #Output remaining sequence
    if ref_seq is not None:
        for i in range(prev_offset, len(ref_seq)):
            seq += ref_seq[i]
        if args.trim_seq:
            return seq[:len(ref_seq)]
    return seq



def writeHeader(popmodel, loci_count, out_f, header="Test IMa input",
                pop_string=None):
    out_f.write(header+'\n')
    out_f.write(str(popmodel.npop)+'\n')
    pops = ''
    for p in popmodel.pop_list:
        pops += (p+' ')
    out_f.write(pops+'\n')
    #Add default treestring when found in IMa3 source
    if pop_string is not None:
        out_f.write(pop_string+'\n')
    out_f.write(str(loci_count)+'\n')

def getLocusHeader(gener, popmodel, rec_list, mut_model="I", inhet_sc=None, mut_rate=1e-9,include_seq=False):
    if inhet_sc is None:
        if gener.chrom in ['X','chrX']:
            inhet_sc = 0.75
        elif gener.chrom in ['Y','chrY','MT','chrMT']:
            inhet_sc = 0.25
        else:
            inhet_sc = 1
    name = gener.chrom+':'+str(gener.start)+':'+str(gener.end)
    gene_len = gener.end-gener.start
    for rec in rec_list:
        gene_len += (getMaxAlleleLength(rec.alleles) - len(rec.ref))
    lh = name
    #for i in range(len(pop_data)):
    #    lh += ' '+str(len(pop_data[i][1]))
    for p in popmodel.pop_list:
        lh += ' '+str(2*popmodel.nind[p])
    if include_seq:
        lh += ' '+str(gene_len)
    else:
        lh += ' '+str(len(rec_list))
    if mut_model not in ['I','H','S','J','IS']:
        raise Exception("%s is an invalid mutation model (must select from I,H,S,J,IS)" % (mut_model))
    lh += ' '+mut_model
    lh += ' '+str(inhet_sc)
    mutlocus = mut_rate * gene_len
    lh += ' '+str("%.14f" % (mutlocus))
    return lh

def getMultiName(args):
    suffix = '.fasta' if args.fasta else '.u'
    i = 1
    while True:
        yield args.multi_out+'_region'+str(i)+suffix
        i += 1

def getOutputFilename(args):
    if args.output_name is not None:
        return args.output_name
    suffix = '.fasta' if args.fasta else '.u'
    va = args.vcfname.split('.')
    if len(va) == 1:
        return va+suffix
    ext_cut = -1
    if va[-1] == 'gz':
        ext_cut = -2
    return '.'.join(va[:ext_cut])+suffix

def hasMissingData(rec_list, indiv_idx):
    for rec in rec_list:
        if rec.samples[indiv_idx].alleles[0] is None:
            return True
    return False


def vcf_to_ima(sys_args):
    """Returns a FASTA file with seqs from individuals in given gene regions

    Given an input VCF file, a reference FASTA file, and a list of gene
    regions, will output a FASTA file with sequence data for all individuals
    in the regions given. The reference FASTA file must be a full file from
    one or multiple chromosomes, starting at the first base. The gene
    region file must have start and end coordinates (half-open), with an
    optional column for chromosome data if the VCF input has multiple
    chromosomes.

    Parameters
    ----------
    --vcf : str
        Filename for VCF input file. If it does not end with extension
        'vcf(.gz)', a value for --ext must be provided.
    --ref : str
        Filename for FASTA reference file. This file can contain multiple
        chromosomes but must start from the first base, as there is currently
        no way to offset the sequences when pulling from a Region
    --rl : str
        Filename for gene region file. Requires columns for start and end
        coordinates, with option for chromosome. Additional data may be
        included, the columns with relevant data can be specified with the
        --gene-col option
    --indels : bool, optional
        If set, indels will be included in the output sequences
    --output : str, optional
        If set, the default output name of (inputprefix).fasta will be
        replaced with the given string
    --gene-col : str, optional
        Comma-separated string with two or three elements (chromosome is
        optional). If length is 2, elements are the indices for columns
        in the input gene region file corresponding to the start/end
        coordinates of a region. If length 3, the third element
        specifies the index of the chromosome column. Default is "1,2,0",
        to match column order in a BED file.



    Other Parameters
    ----------------
    --gr1 : bool, optional (False)
        If set, indicates that the genome coordinate data is in base 1
    --trim-to-ref-length: bool, optional (False)
        If set, the sequences output will always match the length of the
        region they are found in. For example, a sequence with an insertion
        will cause the sequence to be an additional length of n-1, with n
        being the length of the insertion.
    --compress-vcf : bool, optional
        If set, will use bgzip and tabix to compress and index given VCF
        file
    --subsamp-list : str, optional
        Name of single-column file with names of individuals to subsample
        from input VCF file.
    --subsamp-num : int, optional
        Number of individuals to be randomly subsampled from VCF file

    Output
    ------
    IMa file
        Will be named either '--output' value or (vcfinput).ima.u.
        Contains variants in designated loci for IMa run.
    """
    parser = createParser()
    if len(sys_args) == 0:
        parser.print_help()
        sys.exit(1)

    required_args = ['vcfname','popname']
    args = getArgsWithConfig(parser,sys_args,required_args,'vcf_to_ima')
    checkArgs(args)
    logArgs(args)
    #validateFiles(args)
    if args.multi_out is None:
        output_filename = getOutputFilename(args)
        output_file = open(output_filename, 'w')
    else:
        outnamegen = getMultiName(args)
    popmodel = None
    use_allpop = False
    if args.popname is not None:
        popmodels = read_model_file(args.popname)
        if len(popmodels) != 1:
            popmodel = popmodels[args.poptag]
        else:
            pp = list(popmodels.keys())
            popmodel = popmodels[pp[0]]
    else:
        use_allpop = True

    filter_recs = (args.remove_multiallele or (args.remove_missing != -1) or not args.indel_flag or args.parsecpg)

    if args.vcfname is not None:
        single_file = True
    elif args.vcflist is not None:
        single_file = False
    else:
        raise Exception("VCF tag must be specified")
    if single_file:
        vn = args.vcfname
    else:
        vn = args.vcflist[0]
    vcf_reader = vf.VcfReader(vn,
                              compress_flag=args.compress_flag,
                              popmodel=popmodel,
                              use_allpop=use_allpop)
    logging.info('VCF file read')

    regions_provided = False
    if args.genename is not None:
        regions_provided = True
        region_list = RegionList(filename=args.genename, zeroho=args.zeroho,
                            zeroclosed=args.zeroclosed,
                            colstr=args.gene_col)
        logging.info('Region list read')
    fasta_ref = None
    if args.refname is not None:
        fasta_ref = pysam.FastaFile(args.refname)
    record_count = 1
    first_el = vcf_reader.prev_last_rec

    logging.info('Total individuals: %d' % (len(vcf_reader.prev_last_rec.samples)))
    if regions_provided:
        logging.info('Total regions: %d' % (len(region_list.regions)))
    total_regions = (len(region_list.regions) if regions_provided else len(args.vcflist))
    if not args.fasta:
        writeHeader(popmodel, total_regions, output_file)
    if not single_file:
        vcf_reader.reader.close()
    for i in range(total_regions):
        #if regions_provided:
        #region = region_list.regions[i]
        if args.multi_out is not None:
            try:
                output_file.close()
            except:
                pass
            output_filename = next(outnamegen)
            output_file = open(output_filename,'w')
        if single_file:
            region = region_list.regions[i]
            rec_list = vcf_reader.getRecordList(region)
        else:
            vcf_reader = vf.VcfReader(args.vcflist[i],
                                      compress_flag=args.compress_flag,
                                      popmodel=popmodel,
                                      use_allpop=use_allpop)
            rec_list = vcf_reader.getRecordList()
            vcf_reader.reader.close()
            if regions_provided:
                region = region_list.regions[i]
            else:
                region = Region(rec_list[0].pos-1,rec_list[-1].pos,rec_list[0].chrom)
        if filter_recs:
            t = vf.filterSites(rec_list,remove_cpg=args.parsecpg,remove_indels=(not args.indel_flag),remove_multiallele=args.remove_multiallele,remove_missing=args.remove_missing,inform_level=1,fasta_ref=fasta_ref)
            rec_list = t
        if len(rec_list) == 0:
            logging.warning(("Region %s has no variants "
                            "in VCF file") % (region.toStr()))
        logging.debug('Region %d to %d: %d variants' %
                      (region.start,region.end,len(rec_list)))
        ref_seq = None
        if fasta_ref is not None:
            try:
                ref_seq = fasta_ref.fetch(region.chrom, region.start, region.end)
            except KeyError:
                ref_seq = fasta_ref.fetch(vf.flipChrom(region.chrom),region.start,region.end)
            checkRefAlign(rec_list, fasta_ref, region.chrom, args.ref_check)
        if not args.fasta:
            temp_locus = locus(region, rec_list, popmodel, args)
            #reg_header = getLocusHeader(region, popmodel, rec_list,mut_rate=args.mutrate,inhet_sc=args.inhet_sc,include_seq=(fasta_ref is not None))
            #output_file.write(reg_header+'\n')
        popnum = 0
        #for p in popmodel.pop_list:
        for p in vcf_reader.popkeys.keys():
            for indiv,indiv_idx in enumerate(vcf_reader.popkeys[p]):
                if indiv_idx == -1:
                    continue
                for hap in range(len(first_el.samples[indiv_idx].alleles)):
                    if args.fasta:
                        seq = generateSequence(rec_list, ref_seq,
                                   region, region.chrom, indiv_idx, hap, args)
                        output_file.write('>'+first_el.samples[indiv_idx].name+'_'+str(hap)+'\n')
                        output_file.write(seq+'\n')
                        continue
                    hmd = hasMissingData(rec_list,indiv_idx)
                    if hmd:
                        if not args.drop_inds:
                            raise Exception("Individual %d from pop %s at loci %d, site %d is missing data" % (indiv_idx,p,record_count,i))
                        else:
                            continue

                    seq = generateSequence(rec_list, ref_seq,
                                   region, region.chrom, indiv_idx, hap, args)
                    seq_name = str(popnum)+':'+str(indiv)+':'+str(hap)
                    seq_name += ''.join([' ' for i in range(len(seq_name),10)])
                    allseq = seq_name + seq
                    temp_locus.addSeq(allseq,p)
                    #output_file.write(seq_name)

                    #output_file.write(seq+'\n')
                #indiv += 1
            popnum += 1
            indiv = 0
        temp_locus.printToFile(outf = output_file)
        record_count += 1
    output_file.close()

if __name__ == "__main__":
    initLogger()
    vcf_to_ima(sys.argv[1:])