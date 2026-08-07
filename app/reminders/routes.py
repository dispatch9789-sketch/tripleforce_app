"""Reminders blueprint: follow-up and reminder system."""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required

from app.extensions import db
from app.models import Reminder, Customer, REMINDER_TYPES
from app.forms import ReminderForm
from app.utils import dispatcher_or_above

reminders = Blueprint("reminders", __name__)


@reminders.route("/")
@login_required
@dispatcher_or_above
def index():
    show = request.args.get("show", "all")  # all, upcoming, overdue, completed

    query = Reminder.query
    if show == "upcoming":
        query = query.filter(Reminder.is_completed == False, Reminder.due_date >= date.today())
    elif show == "overdue":
        query = query.filter(Reminder.is_completed == False, Reminder.due_date < date.today())
    elif show == "completed":
        query = query.filter(Reminder.is_completed == True)

    reminders_list = query.order_by(Reminder.due_date).all()
    return render_template("reminders/index.html", reminders=reminders_list, show=show)


@reminders.route("/new", methods=["GET", "POST"])
@login_required
@dispatcher_or_above
def new():
    form = ReminderForm()
    customers = Customer.query.filter_by(is_archived=False).order_by(Customer.business_name).all()
    form.customer_id.choices = [(0, "— No Customer —")] + [(c.id, c.business_name) for c in customers]

    if form.validate_on_submit():
        customer_id = form.customer_id.data if form.customer_id.data and form.customer_id.data > 0 else None
        reminder = Reminder(
            customer_id=customer_id,
            title=form.title.data,
            reminder_type=form.reminder_type.data,
            description=form.description.data,
            due_date=form.due_date.data,
            priority=form.priority.data,
        )
        db.session.add(reminder)
        db.session.commit()
        flash("Reminder created.", "success")
        return redirect(url_for("reminders.index"))
    return render_template("reminders/form.html", form=form, title="New Reminder")


@reminders.route("/<int:reminder_id>/complete", methods=["POST"])
@login_required
@dispatcher_or_above
def complete(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    reminder.is_completed = True
    reminder.completed_at = date.today()
    db.session.commit()
    flash("Reminder marked complete.", "success")
    return redirect(url_for("reminders.index"))


@reminders.route("/<int:reminder_id>/delete", methods=["POST"])
@login_required
@dispatcher_or_above
def delete(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    db.session.delete(reminder)
    db.session.commit()
    flash("Reminder deleted.", "info")
    return redirect(url_for("reminders.index"))
