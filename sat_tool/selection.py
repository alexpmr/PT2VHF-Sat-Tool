"""Pure helpers for persistent satellite marking, batch downloads, and CAT safety."""
from __future__ import annotations


def change_selection(orbit_objects, filtered_ids, current_ids, select, filtered):
    """Return (explicit NORAD IDs, affected IDs), never dependent on frequency caches.

    Manual selection is independent of compatible-frequency discovery.
    """
    available={str(ident) for ident in orbit_objects}
    affected=({str(ident) for ident in filtered_ids} & available) if filtered else available
    current={str(ident) for ident in current_ids} & available
    updated=(current|affected) if select else (current-affected)
    return sorted(updated),sorted(affected)


def transmitter_batch_ids(scope, chosen_id, enabled_ids, filtered_ids, orbit_objects):
    """Resolve a scope using stable indices, including the entire orbital catalog."""
    if scope==0:
        proposed=[chosen_id] if chosen_id is not None else []
    elif scope==1:
        proposed=enabled_ids
    elif scope==2:
        proposed=filtered_ids
    elif scope==3:
        # Full orbital catalog: never limit frequency updates to favorites,
        # the current row or a search filter.
        proposed=list(orbit_objects)
    else:
        raise ValueError("Escopo de atualização SatNOGS inválido")
    available={str(ident) for ident in orbit_objects}
    return list(dict.fromkeys(str(ident) for ident in proposed if ident is not None
                              and str(ident) in available))


def cat_doppler_allowed(visible, explicit_outside_permission=False):
    """The GUI preview never calls this gate; only CAT retuning does."""
    return bool(visible or explicit_outside_permission)
