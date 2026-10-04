"""Session-backed comparison actions shared by enhanced and normal requests."""
def clear_comparison(session):
    session['comparison'] = []
    session.pop('comparison_error', None)
