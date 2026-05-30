"""EuroPriv-Bench — a unified pan-European de-identification benchmark.

The benchmark scores PII/PHI detection, anonymization, privacy classification, and the
privacy-utility / re-identification-risk tradeoff across European languages and the legal
and clinical domains, under one harmonized GDPR-aligned taxonomy.

Design goal: be the neutral yardstick the whole field is ranked on. The harness core is
dependency-light (pydantic + pyyaml + seqeval); model backends (transformers, GLiNER,
Presidio) are optional extras behind the `adapters` layer.
"""

__version__ = "0.2.0"
