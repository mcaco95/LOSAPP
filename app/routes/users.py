from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from ..decorators import admin_required
from ..models.user import User, db
from ..forms import AdminUserForm, AdminUserEditForm

users = Blueprint('users', __name__)

@users.route('/users')
@login_required
@admin_required
def index():
    users_list = User.query.all()
    return render_template('users/index.html', users=users_list)

@users.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = AdminUserForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating user. Email might be already taken.', 'error')
    return render_template('users/create.html', form=form)

@users.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    user = User.query.get_or_404(id)
    form = AdminUserEditForm(obj=user)
    
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        if form.password.data:
            user.set_password(form.password.data)
        try:
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating user. Email might be already taken.', 'error')
    
    return render_template('users/edit.html', form=form, user=user)

@users.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    user = User.query.get_or_404(id)
    if user.email == 'simon@logisticsonesource.com':
        flash('Cannot delete admin user!', 'error')
        return redirect(url_for('users.index'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting user.', 'error')
    
    return redirect(url_for('users.index'))
