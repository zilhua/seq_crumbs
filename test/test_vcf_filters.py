'''
Created on 2013 eka 7

@author: peio
'''
from os.path import join, dirname
import unittest
import math
from tempfile import NamedTemporaryFile
from copy import deepcopy, copy
from subprocess import check_output

from vcf import Reader

from vcf_crumbs.vcf_filters import (calculate_maf, CloseToSnvFilter,
                                    MafLimitFilter, HighVariableRegionFilter,
                                    CloseToLimitFilter, IsVariableFilter,
                                    CapEnzymeFilter, count_alleles,
                                    IsNotVariableFilter, ChangeAminoFilter,
                                    ChangeAminoSeverityFilter)
from vcf_crumbs.utils.path_utils import TEST_DATA_DIR


VCF_PATH = join(TEST_DATA_DIR, 'sample.vcf.gz')
VCF_INDEL_PATH = join(TEST_DATA_DIR, 'sample_indel.vcf.gz')
REF_PATH = join(TEST_DATA_DIR, 'sample_ref.fasta')
VARI_VCF_PATH = join(TEST_DATA_DIR, 'vari_filter.vcf')
GATK_VCF_PATH = join(TEST_DATA_DIR, 'gatk_sample.vcf.gz')


def floats_are_equal(num1, num2):
    'Given two numbers it returns True if they are similar'
    if num1 == 0.0:
        if num2 == 0.0:
            return True
        else:
            return False
    log1 = math.log(float(num1))
    log2 = math.log(float(num2))
    return abs(log1 - log2) < 0.01


class AnnotateRecordTests(unittest.TestCase):

    def test_mac_calcule(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        assert floats_are_equal(calculate_maf(rec1), 0.526315789474)

    def test_calculate_alleles(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        counts = count_alleles(rec1, sample_names=['pepo', 'mu16'])['mu16']
        assert counts == {'A': 10}
        counts = count_alleles(rec1)['all']
        assert counts == {'A': 10, 'C': 9}

        records = Reader(filename=GATK_VCF_PATH)
        rec1 = records.next()
        counts = count_alleles(rec1)
        assert counts == {'all': {'T': 5, 'G': 2}}
        for record in Reader(filename=GATK_VCF_PATH):
            if record.CHROM == 'CAUC00157_TC01' and record.POS == 198:
                counts = count_alleles(record)
                assert counts == {'all': {'C': 10, 'G': 41}}


class FakeClass(object):
    FILTER = []
    INFO = {}

    def add_filter(self, name):
        self.FILTER.append(name)

    def add_info(self, info, value):
        self.INFO[info] = value


class FilterTest(unittest.TestCase):

    def test_close_to_filter(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = CloseToSnvFilter(distance=60, max_maf=None,
                                   vcf_fpath=VCF_PATH)
        rec1 = filter_(rec1)
        assert filter_.name in rec1.FILTER

        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = CloseToSnvFilter(distance=60, max_maf=0.5,
                                   vcf_fpath=VCF_PATH)

        rec1 = filter_(rec1)
        assert not filter_.name in rec1.FILTER

        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = CloseToSnvFilter(distance=60, max_maf=0.6,
                                   vcf_fpath=VCF_PATH)
        rec1 = filter_(rec1)
        assert filter_.name in rec1.FILTER
        assert filter_.name == 'cs60_0.60'
        desc = 'The snv is closer than 60 nucleotides to another snv, '
        desc += 'with maf:0.60'
        assert desc in filter_.description

    def test_high_variable_region_filter(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = HighVariableRegionFilter(max_variability=0.002,
                                           window=None,
                                           vcf_fpath=VCF_PATH,
                                           ref_fpath=REF_PATH)
        rec1 = filter_(rec1)
        assert filter_.name in rec1.FILTER

        filter_ = HighVariableRegionFilter(max_variability=0.005,
                                           window=None,
                                           vcf_fpath=VCF_PATH,
                                           ref_fpath=REF_PATH)
        rec1 = filter_(rec1)
        assert not filter_.name in rec1.FILTER

        assert  filter_.name == 'hv0.005'
        desc = 'The region has more than 0.5 snvs per 100 bases'
        assert desc in filter_.description

    def test_close_to_limit_filter(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = CloseToLimitFilter(distance=60, ref_fpath=REF_PATH)
        rec1 = filter_(rec1)
        assert not filter_.name in rec1.FILTER

        filter_ = CloseToLimitFilter(distance=800, ref_fpath=REF_PATH)
        rec1 = filter_(rec1)
        assert filter_.name in rec1.FILTER

        assert filter_.name == 'cl800'
        desc = 'The snv is closer than 800 nucleotides to the reference edge'
        assert  desc in filter_.description

    def test_maf_limit(self):
        records = Reader(filename=VCF_PATH)
        rec1 = records.next()
        filter_ = MafLimitFilter(max_maf=0.7)
        rec1 = filter_(rec1)
        assert not filter_.name in rec1.FILTER

        filter_ = MafLimitFilter(max_maf=0.5)
        rec1 = filter_(rec1)
        assert filter_.name in rec1.FILTER

        assert  filter_.name == 'maf0.5'
        desc = 'The most frequent allele in samples: all.'
        desc += 'frequency greater than 0.5'
        assert  desc in filter_.description

    def test_cap_enzyme_filter(self):
        seq_str = '>seq1\nATGATGATGgaaattcATGATGATGTGGGAT\n'
        seq_str += '>seq2\nATGATGATGATGATGATGTGGGAT\n'
        fhand = NamedTemporaryFile()
        fhand.write(seq_str)
        fhand.flush()
        filter_ = CapEnzymeFilter(all_enzymes=True, ref_fpath=fhand.name)
        assert filter_.name == 'cet'
        desc = 'SNV is not a CAP detectable by the enzymes: all'
        assert desc in filter_.description

        record = FakeClass()
        record.POS = 11
        record.end = 12
        record.CHROM = 'seq1'
        record.FILTER = []

        alt_allele = FakeClass()
        alt_allele.sequence = 'A'
        record.alleles = ['AA', alt_allele]
        record.FILTER = []
        record.add_filter = lambda x: self.FILTER.append(x)

        rec1 = filter_(record)
        assert not filter_.name in rec1.FILTER

        record = FakeClass()
        record.POS = 12
        record.end = 12
        record.CHROM = 'seq2'
        record.FILTER = []
        record.alleles = ['A', alt_allele]
        rec1 = filter_(record)
        assert filter_.name in rec1.FILTER

    def test_is_variable_filter(self):
        records = Reader(filename=VCF_PATH)
        record = records.next()
        filter_ = IsVariableFilter(max_maf=0.7, samples=['mu16', 'upv196'],
                                    filter_id=1)
        rec1 = filter_(deepcopy(record))
        assert not filter_.name in rec1.FILTER

        # in union False
        filter_ = IsVariableFilter(max_maf=0.7, samples=['mu16', 'upv196'],
                                   in_union=False, filter_id=1)
        rec1 = filter_(deepcopy(record))
        assert filter_.name in rec1.FILTER

        # in all_groups False
        filter_ = IsVariableFilter(max_maf=0.7, samples=['mu16', 'upv196'],
                                   in_union=False, in_all_groups=False,
                                   filter_id=1)
        rec1 = filter_(deepcopy(record))
        assert filter_.name in rec1.FILTER

        records = Reader(filename=VARI_VCF_PATH)
        record = records.next()
        f = IsVariableFilter(max_maf=None, samples=['rg1'], in_union=False,
                             in_all_groups=True, reference_free=True,
                             min_reads=None, min_reads_per_allele=1,
                             filter_id=1)
        rec1 = f(deepcopy(record))
        assert not f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg1'], in_union=True,
                             in_all_groups=True, reference_free=True,
                             min_reads=None, min_reads_per_allele=1,
                             filter_id=1)
        rec1 = f(deepcopy(record))
        assert not f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg1'], in_union=True,
                             in_all_groups=True, reference_free=True,
                             min_reads=None, min_reads_per_allele=2,
                             filter_id=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg2', 'rg4'],
                             in_union=True, in_all_groups=True,
                             reference_free=True, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['fake'],
                             in_union=True, in_all_groups=True,
                             reference_free=True, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg2', 'rg3'],
                             in_union=True, in_all_groups=True,
                             reference_free=True, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)
        rec1 = f(deepcopy(record))
        assert not f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg5'],
                             in_union=True, in_all_groups=True,
                             reference_free=False, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg2'],
                             in_union=True, in_all_groups=True,
                             reference_free=False, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)
        rec1 = f(deepcopy(record))
        assert not f.name in rec1.FILTER

        f = IsVariableFilter(max_maf=None, samples=['rg2'],
                             in_union=True, in_all_groups=True,
                             reference_free=True, min_reads=None,
                             min_reads_per_allele=1, filter_id=1)

        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        assert f.name == 'vs1'
        desc = 'It is not variable, or no data, in the samples : '
        desc += 'rg2. All together: True'
        assert  desc in f.description

    def test_is_not_variable_filter(self):
        records = Reader(filename=VARI_VCF_PATH)
        record = records.next()
        f = IsNotVariableFilter(filter_id=1, samples=['rg1'], in_union=True,
                                reference_free=True, max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'], in_union=True,
                                reference_free=False, max_maf=None,
                                min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'], in_union=False,
                                reference_free=False, max_maf=None,
                                min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg2', 'rg4'],
                                in_union=True, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg3', 'rg4'],
                                in_union=True, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg3', 'rg4'],
                                in_union=False, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg5'],
                                in_union=True, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        record = records.next()
        f = IsNotVariableFilter(filter_id=1, samples=['rg1'],
                                in_union=True, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg2', 'rg4'],
                                in_union=True, reference_free=True,
                                max_maf=None, min_reads=1)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        record = records.next()

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'],
                                in_union=True, reference_free=True,
                                max_maf=0.95, min_reads=50)
        rec1 = f(deepcopy(record))
        assert f.name in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'],
                                in_union=True, reference_free=True,
                                max_maf=0.6, min_reads=50)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'],
                                in_union=True, reference_free=True,
                                max_maf=0.95, min_reads=200)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        f = IsNotVariableFilter(filter_id=1, samples=['rg1'],
                                in_union=True, reference_free=True,
                                max_maf=0.6, min_reads=200)
        rec1 = f(deepcopy(record))
        assert f.name not in rec1.FILTER

        assert f.name == 'nvs1'
        desc = 'It is variable, or no data, in the samples : rg1. '
        desc += 'All together: True'
        assert desc in f.description

    def test_amino_change_filter(self):
        seq_ref = """>SEUC00016_TC01
    CACGCTAAACAACGATCATTGTCATCGGTACCGATTGTTACAAGTTGTGTGCAGTGTCGT
    GCTATTTGTGTGTACATTCCTTCTAAGATGTCGTCAACAAAGTGGTTGGTGTGTGCGCTA
    GTGGTGGTGTGCGTGAGCGTAAGGCAAGCAACATCTGCGCCGGCGCCGCAGGAACAAGAA
    TACCCGCCTATGCCCTACGAGTACAAATATGACGTTGAAGATCAAGAGCTTGAAGAGAAA
    GCTCTCTACTTCGGAGCCAACGAAGCAGGAGATGCCCAGGGCAAGGTCATCGGAGGATAC
    CGAGTTCTCCTCCCCGATGGTCGTCTTATGACCGTCGAGTACAGTGTGGAGGGAGAAAGC
    GGTTTCGTTCCCAAAATCACCTTCGAAGACAACGCCAGCCCCTTCGGCAAAGGAAAGTAG
    ACCTTATAACGACGCCTACAAGACTGGTACCGCGATCAATTGATACTAGTTCAATTTGAT
    TTCTGAATTCTATGCCGTAAAACATTTTCTTTTATTAATTATACCGATTTCGATAAATAG
    ACATCTTTACCTACTTAACGAATTTCTCATAGGATTCAGAAGTCGAAACCGAAAAAAGTT
    ACTTCAGTTTTCATTAGATTGTAAATGTGTGTAAATTATTATTATTATTATATCAGGGAT
    CCTTAAGTTGATATTAGTGGTGATATAAACGATATTTATGAACGACAATCAGGTATCGTC
    ACTGGCTTGAGTAATGTTAGAAAAAATATAATTTTACCGAAAGCATTAGTAACTTTTTTC
    ACGATTATAATCTCCCATACATACTGTATACTTACGTTACGTATAATAATTTTGATTGTC
    TTCATAGTGTACTCTATAATATATGTAGGTGTAGGCAAAACTCATTCGCCAATAAGATAA
    TATGTACAGTCAGCGATTTCTAAGATAAATTTGTACCGCAAATATCGAGTTACCGATACT
    GTGATCAATTAGAACG"""
        orf_seq = '''>SEUC00016_TC01_orf_seq start=89 end=421 strand=forward
    ATGTCGTCAACAAAGTGGTTGGTGTGTGCGCTAGTGGTGGTGTGCGTGAGCGTAAGGCAAGCAACATCTGCGC
    CGGCGCCGCAGGAACAAGAATACCCGCCTATGCCCTACGAGTACAAATATGACGTTGAAGATCAAGAGCTTGAA
    GAGAAAGCTCTCTACTTCGGAGCCAACGAAGCAGGAGATGCCCAGGGCAAGGTCATCGGAGGATACCGAGTTCT
    CCTCCCCGATGGTCGTCTTATGACCGTCGAGTACAGTGTGGAGGGAGAAAGCGGTTTCGTTCCCAAAATCACCT
    TCGAAGACAACGCCAGCCCCTTCGGCAAAGGAAAGTAG'''
        ref_fhand = NamedTemporaryFile()
        ref_fhand.write(seq_ref)
        ref_fhand.flush()

        orf_fhand = NamedTemporaryFile()
        orf_fhand.write(orf_seq)
        orf_fhand.flush()

        f = ChangeAminoFilter(ref_fpath=ref_fhand.name,
                              orf_seq_fpath=orf_fhand.name)

        record = FakeClass()
        alt_allele = FakeClass()
        alt_allele.sequence = 'C'
        record.CHROM = 'SEUC00016_TC01'
        record.is_indel = False
        record.POS = 112
        record.alleles = ['T', alt_allele]
        record = f(record)
        assert f.name in record.FILTER
        assert record.INFO == {'AAC': 'C->R'}

        f = ChangeAminoSeverityFilter(ref_fpath=ref_fhand.name,
                                      orf_seq_fpath=orf_fhand.name)
        record = FakeClass()
        alt_allele = FakeClass()
        alt_allele.sequence = 'C'
        record.CHROM = 'SEUC00016_TC01'
        record.is_indel = False
        record.POS = 112
        record.alleles = ['T', alt_allele]
        record = f(record)
        assert f.name in record.FILTER

    def xtest_vcfparser(self):
        reader = Reader(open(VCF_INDEL_PATH))
        for snp in reader:
            print "***************"
            print snp.REF
            print type(snp.ALT[0])
            print snp.alleles
            print 'info', snp.INFO
            for call in snp.samples:
                if call.gt_bases is None:
                    continue
                print call.gt_alleles
                print call.gt_nums.split('/')
                print call.data
                print call.site
            print 'pos', snp.POS
            print 'end', snp.end
            print snp.is_snp


class BinaryTest(unittest.TestCase):
    def test_run_binary(self):
        binary = join(dirname(__file__), '..', 'bin', 'run_vcf_filters.py')
        assert 'usage' in check_output([binary, '-h'])

        conf = join(TEST_DATA_DIR, 'filter_conf')
        cmd = [binary, VCF_PATH, '-f', conf]
        result = check_output(cmd)
        assert 'cs60_0.70\t' in result
        assert 'CAP=SetI' in result


if __name__ == "__main__":
#     import sys;sys.argv = ['', 'FilterTest.test_close_to_filter']
    unittest.main()
