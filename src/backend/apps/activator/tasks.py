from celery import shared_task


@shared_task(name="apps.activator.tasks.evaluate_activator_rules", queue="activator")
def evaluate_activator_rules() -> dict:
    """Évalue toutes les règles Activator actives — implémenté dans 08-forge-activator.md."""
    from .models import ActivatorRule

    rules = ActivatorRule.objects.filter(is_active=True, circuit_open=False)
    evaluated = 0
    for rule in rules:
        _evaluate_rule(rule)
        evaluated += 1
    return {"evaluated": evaluated}


def _evaluate_rule(rule) -> None:
    """Placeholder — la logique complète est dans le guide Forge Activator."""
    pass
