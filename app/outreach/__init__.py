"""Outreach Tracker blueprint — B2B prospect & follow-up pipeline.

The database is the single source of truth: every action (add, edit, mark-sent,
follow-up, response, vendor status, stage, notes, archive) commits a row to the
``prospects`` table. The CSV is an import source only — never read at render time.
"""
