"""Outreach Tracker routes — prospect pipeline backed by the ``prospects`` table."""
import csv
from datetime import date, datetime

import click
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Prospect, OUTREACH_STATUSES, OPPORTUNITY_STAGES, VENDOR_REGISTRATION_STATUSES,
)
from app.forms import ProspectForm, ProspectStatusForm, ProspectNotesForm, ProspectFollowUpForm, ProspectImportForm
from app.utils import dispatcher_or_above

outreach = Blueprint("outreach", __name__)


# ── CSV column → Prospect field (directly mapped) ─────────────────────────
CSV_FIELD_MAP = {
    "Organization": "organization_name",
    "Facility Type": "organization_type",
    "Website": "website",
    "Verified Contact": "contact_person",
    "Contact Title/Department": "contact_title",
    "Email": "email",
    "Phone": "phone",
    "Vendor/Procurement Portal": "procurement_vendor_route",
    "Status": "outreach_status",
    "Date Contacted": "date_contacted",
    "Subject": "outreach_subject",
    "Follow-up 1 Date": "follow_up_date",
    "Response Summary": "response_status",
    "Vendor App Submitted Date": "vendor_application_date",
    "Opportunity Stage": "opportunity_stage",
}

# Extra CSV columns folded into the Notes field on import.
EXTRA_TO_NOTES = [
    "Location", "Outreach Method", "Priority", "Courier Need Signal",
    "Delivery/Status", "Follow-up 1 Status", "Follow-up 2 Date",
    "Follow-up 2 Status", "Last Response Date", "Procurement Referral",
    "Meeting Requested Date", "Opt-out",
]

_STATUS_ALIASES = {
    "not contacted": "Drafted - Pending Approval",
    "drafted": "Drafted - Pending Approval",
    "drafted - pending approval": "Drafted - Pending Approval",
    "ready": "Ready to Send",
    "ready to send": "Ready to Send",
    "sent": "Sent",
    "follow-up needed": "Follow-Up Needed",
    "follow up needed": "Follow-Up Needed",
    "responded": "Responded",
    "closed": "Closed",
}


# ── Helpers ────────────────────────────────────────────────────────────────
def _parse_date(raw):
    """Parse common date formats; return None for blank/unparseable values."""
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_status(raw):
    value = (raw or "").strip().lower()
    if not value:
        return "Drafted - Pending Approval"
    return _STATUS_ALIASES.get(value, "Drafted - Pending Approval" if value not in [s.lower() for s in OUTREACH_STATUSES] else raw.strip())


def _normalize_stage(raw):
    value = (raw or "").strip()
    if not value:
        return "Prospect"
    if value in OPPORTUNITY_STAGES:
        return value
    lowered = value.lower()
    for stage in OPPORTUNITY_STAGES:
        if stage.lower() == lowered:
            return stage
    return "Prospect"


def _set_choices(form):
    """Populate SelectField choices from the model constants (only fields present)."""
    if hasattr(form, "outreach_status"):
        form.outreach_status.choices = [(s, s) for s in OUTREACH_STATUSES]
    if hasattr(form, "opportunity_stage"):
        form.opportunity_stage.choices = [(s, s) for s in OPPORTUNITY_STAGES]
    if hasattr(form, "vendor_registration_status"):
        form.vendor_registration_status.choices = [(s, s) for s in VENDOR_REGISTRATION_STATUSES]


def _find_duplicate(dedupe_key, exclude_id=None):
    query = Prospect.query.filter_by(dedupe_key=dedupe_key)
    if exclude_id is not None:
        query = query.filter(Prospect.id != exclude_id)
    return query.first()


def _populate_from_form(prospect, form):
    """Copy validated form data onto the prospect and recompute its dedupe key."""
    prospect.organization_name = form.organization_name.data.strip()
    prospect.organization_type = form.organization_type.data or None
    prospect.contact_person = form.contact_person.data or None
    prospect.contact_title = form.contact_title.data or None
    prospect.email = form.email.data or None
    prospect.phone = form.phone.data or None
    prospect.website = form.website.data or None
    prospect.procurement_vendor_route = form.procurement_vendor_route.data or None
    prospect.outreach_subject = form.outreach_subject.data or None
    prospect.outreach_status = form.outreach_status.data or "Drafted - Pending Approval"
    prospect.date_contacted = form.date_contacted.data
    prospect.follow_up_date = form.follow_up_date.data
    prospect.response_status = form.response_status.data or None
    prospect.vendor_application_date = form.vendor_application_date.data
    prospect.vendor_registration_status = form.vendor_registration_status.data or "Not Started"
    prospect.opportunity_stage = form.opportunity_stage.data or "Prospect"
    prospect.notes = form.notes.data or None
    # Always recompute so edits to org/email/phone/website keep dedupe accurate.
    prospect.dedupe_key = Prospect.build_dedupe_key(
        prospect.organization_name, prospect.email or "",
        prospect.phone or "", prospect.website or "")
    return prospect


def _dashboard_counts():
    """Eight live metrics computed from the prospects table."""
    active = Prospect.query.filter_by(archived=False)
    total = active.count()
    not_contacted = active.filter(
        Prospect.date_contacted.is_(None),
        Prospect.outreach_status.in_(["Drafted - Pending Approval", "Ready to Send"]),
    ).count()
    contacted = active.filter(Prospect.date_contacted.is_not(None)).count()
    today = date.today()
    follow_ups_due = active.filter(
        Prospect.follow_up_date.is_not(None),
        Prospect.follow_up_date <= today,
        ~Prospect.outreach_status.in_(["Closed", "Responded"]),
    ).count()
    responses = active.filter(
        Prospect.response_status.is_not(None),
        Prospect.response_status != "",
    ).count()
    vendor_applications = active.filter(
        Prospect.vendor_registration_status.in_(
            ["Application Submitted", "Under Review", "Approved"]
        )
    ).count()
    approved_vendors = active.filter(
        db.or_(
            Prospect.vendor_registration_status == "Approved",
            Prospect.opportunity_stage == "Approved Vendor",
        )
    ).count()
    contract_opportunities = active.filter(
        Prospect.opportunity_stage.in_(["Contract Opportunity", "Won"])
    ).count()
    return {
        "total": total,
        "not_contacted": not_contacted,
        "contacted": contacted,
        "follow_ups_due": follow_ups_due,
        "responses": responses,
        "vendor_applications": vendor_applications,
        "approved_vendors": approved_vendors,
        "contract_opportunities": contract_opportunities,
    }


def import_csv_rows(rows):
    """Import CSV dict-rows into prospects (idempotent, deduped).

    Returns {imported, skipped, failed, errors}. Re-running never duplicates;
    existing prospects are preserved unless explicitly edited.
    """
    imported = skipped = failed = 0
    errors = []
    for line_no, row in enumerate(rows, start=2):  # 1 = header
        org = (row.get("Organization") or "").strip()
        if not org:
            failed += 1
            errors.append(f"Row {line_no}: missing Organization")
            continue
        email = (row.get("Email") or "").strip()
        phone = (row.get("Phone") or "").strip()
        website = (row.get("Website") or "").strip()
        key = Prospect.build_dedupe_key(org, email, phone, website)
        if key and Prospect.query.filter_by(dedupe_key=key).first():
            skipped += 1
            continue

        prospect = Prospect()
        prospect.organization_name = org
        prospect.organization_type = (row.get("Facility Type") or "").strip() or None
        prospect.website = website or None
        prospect.contact_person = (row.get("Verified Contact") or "").strip() or None
        prospect.contact_title = (row.get("Contact Title/Department") or "").strip() or None
        prospect.email = email or None
        prospect.phone = phone or None
        prospect.procurement_vendor_route = (row.get("Vendor/Procurement Portal") or "").strip() or None
        prospect.outreach_subject = (row.get("Subject") or "").strip() or None
        prospect.outreach_status = _normalize_status(row.get("Status"))
        prospect.date_contacted = _parse_date(row.get("Date Contacted"))
        prospect.follow_up_date = _parse_date(row.get("Follow-up 1 Date"))
        resp = (row.get("Response Summary") or "").strip()
        prospect.response_status = None if resp.lower() in ("", "not contacted", "none") else resp
        prospect.vendor_application_date = _parse_date(row.get("Vendor App Submitted Date"))
        prospect.vendor_registration_status = "Not Started"
        prospect.opportunity_stage = _normalize_stage(row.get("Opportunity Stage"))

        notes_parts = []
        base_notes = (row.get("Notes") or "").strip()
        if base_notes:
            notes_parts.append(base_notes)
        for col in EXTRA_TO_NOTES:
            val = (row.get(col) or "").strip()
            if val:
                notes_parts.append(f"{col}: {val}")
        prospect.notes = "\n".join(notes_parts) if notes_parts else None
        prospect.dedupe_key = key

        db.session.add(prospect)
        try:
            db.session.commit()
            imported += 1
        except IntegrityError:
            db.session.rollback()
            skipped += 1
    return {"imported": imported, "skipped": skipped, "failed": failed, "errors": errors}


# ── Dashboard + list ──────────────────────────────────────────────────────
@outreach.route("/")
@login_required
@dispatcher_or_above
def index():
    status = request.args.get("status", "")
    stage = request.args.get("stage", "")
    search = request.args.get("q", "")
    show_archived = request.args.get("archived", "") == "1"

    query = Prospect.query
    if not show_archived:
        query = query.filter(Prospect.archived == False)
    if status:
        query = query.filter(Prospect.outreach_status == status)
    if stage:
        query = query.filter(Prospect.opportunity_stage == stage)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Prospect.organization_name.ilike(like),
                Prospect.contact_person.ilike(like),
                Prospect.email.ilike(like),
                Prospect.organization_type.ilike(like),
            )
        )
    prospects = query.order_by(Prospect.organization_name).all()
    return render_template(
        "outreach/index.html",
        prospects=prospects,
        counts=_dashboard_counts(),
        status=status, stage=stage, search=search, show_archived=show_archived,
        outreach_statuses=OUTREACH_STATUSES,
        opportunity_stages=OPPORTUNITY_STAGES,
        today=date.today(),
    )


# ── Detail ────────────────────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>")
@login_required
@dispatcher_or_above
def view(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    return render_template("outreach/view.html", prospect=prospect, today=date.today())


# ── Add ────────────────────────────────────────────────────────────────────
@outreach.route("/new", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def new():
    form = ProspectForm()
    _set_choices(form)
    if form.validate_on_submit():
        prospect = _populate_from_form(Prospect(), form)
        conflict = _find_duplicate(prospect.dedupe_key)
        if conflict:
            form.organization_name.errors.append(
                "A prospect with this organization and contact info already exists.")
            return render_template("outreach/form.html", form=form, title="Add Prospect")
        db.session.add(prospect)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.organization_name.errors.append(
                "A prospect with this organization and contact info already exists.")
            return render_template("outreach/form.html", form=form, title="Add Prospect")
        flash(f"Added prospect '{prospect.organization_name}'.", "success")
        return redirect(url_for("outreach.view", prospect_id=prospect.id))
    return render_template("outreach/form.html", form=form, title="Add Prospect")


# ── Edit ──────────────────────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>/edit", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def edit(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    form = ProspectForm(obj=prospect)
    _set_choices(form)
    if form.validate_on_submit():
        _populate_from_form(prospect, form)  # always recompute the dedupe key
        conflict = _find_duplicate(prospect.dedupe_key, exclude_id=prospect.id)
        if conflict:
            form.organization_name.errors.append(
                "Another prospect already has this organization and contact info.")
            return render_template("outreach/form.html", form=form, title="Edit Prospect")
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            form.organization_name.errors.append(
                "Another prospect already has this organization and contact info.")
            return render_template("outreach/form.html", form=form, title="Edit Prospect")
        flash(f"Updated '{prospect.organization_name}'.", "success")
        return redirect(url_for("outreach.view", prospect_id=prospect.id))
    return render_template("outreach/form.html", form=form, title="Edit Prospect")


# ── Mark sent ─────────────────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>/mark-sent", methods=["POST"])
@login_required
@dispatcher_or_above
def mark_sent(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    prospect.outreach_status = "Sent"
    if not prospect.date_contacted:
        prospect.date_contacted = date.today()
    db.session.commit()
    flash(f"Marked '{prospect.organization_name}' as Sent.", "success")
    return redirect(url_for("outreach.view", prospect_id=prospect.id))


# ── Follow-up date ────────────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>/followup", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def followup(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    form = ProspectFollowUpForm(obj=prospect)
    _set_choices(form)
    if form.validate_on_submit():
        prospect.follow_up_date = form.follow_up_date.data
        prospect.outreach_status = form.outreach_status.data
        db.session.commit()
        flash("Follow-up date saved.", "success")
        return redirect(url_for("outreach.view", prospect_id=prospect.id))
    return render_template("outreach/followup.html", form=form, prospect=prospect)


# ── Status / stage / vendor status / response ────────────────────────────
@outreach.route("/<int:prospect_id>/status", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def status(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    form = ProspectStatusForm(obj=prospect)
    _set_choices(form)
    if form.validate_on_submit():
        prospect.outreach_status = form.outreach_status.data
        prospect.opportunity_stage = form.opportunity_stage.data
        prospect.vendor_registration_status = form.vendor_registration_status.data
        prospect.response_status = form.response_status.data or None
        db.session.commit()
        flash("Status updated.", "success")
        return redirect(url_for("outreach.view", prospect_id=prospect.id))
    return render_template("outreach/status.html", form=form, prospect=prospect)


# ── Notes (append) ────────────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>/notes", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def notes(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    form = ProspectNotesForm()
    if form.validate_on_submit():
        addition = (form.notes.data or "").strip()
        if addition:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            existing = (prospect.notes or "").rstrip()
            prospect.notes = f"{existing}\n\n[{stamp}] {addition}".strip() if existing else f"[{stamp}] {addition}"
            db.session.commit()
            flash("Note added.", "success")
        return redirect(url_for("outreach.view", prospect_id=prospect.id))
    return render_template("outreach/notes.html", form=form, prospect=prospect)


# ── Archive (soft delete) ────────────────────────────────────────────────
@outreach.route("/<int:prospect_id>/delete", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def delete(prospect_id):
    prospect = Prospect.query.get_or_404(prospect_id)
    if request.method == "POST":
        prospect.archived = True
        db.session.commit()
        flash(f"Archived '{prospect.organization_name}'.", "success")
        return redirect(url_for("outreach.index"))
    return render_template("outreach/delete.html", prospect=prospect)


# ── CSV import ────────────────────────────────────────────────────────────
@outreach.route("/import", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def import_csv():
    form = ProspectImportForm()
    if form.validate_on_submit():
        upload = form.csv_file.data
        stream = upload.stream.read().decode("utf-8-sig")
        rows = list(csv.DictReader(stream.splitlines()))
        result = import_csv_rows(rows)
        flash(
            f"Import complete — Imported: {result['imported']}, "
            f"Skipped: {result['skipped']}, Failed: {result['failed']}.",
            "success",
        )
        if result["errors"]:
            for err in result["errors"]:
                flash(err, "warning")
        return redirect(url_for("outreach.index"))
    return render_template("outreach/import.html", form=form)


# ── CLI: flask outreach-import <path> ──────────────────────────────────────
def register_cli(app):
    @app.cli.command("outreach-import")
    @click.argument("csv_path", type=click.Path(exists=True))
    def _outreach_import(csv_path):
        """Import prospects from a CSV (idempotent, deduped)."""
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        result = import_csv_rows(rows)
        click.echo(f"Imported: {result['imported']}")
        click.echo(f"Skipped (duplicate): {result['skipped']}")
        click.echo(f"Failed: {result['failed']}")
        for err in result["errors"]:
            click.echo(f"  - {err}")
