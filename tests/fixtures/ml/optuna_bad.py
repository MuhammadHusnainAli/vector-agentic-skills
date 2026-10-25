import optuna
from sklearn.model_selection import KFold, cross_val_score
from sklearn.metrics import log_loss


def objective(trial):
    lr = trial.suggest_loguniform("lr", 1e-3, 0.3)
    depth = trial.suggest_int("depth", 2, 8)
    n_layers = 3
    for i in range(n_layers):
        trial.suggest_int(f"units_{i}", 8, 128)
    depth = trial.suggest_float("depth", 2, 8)
    cv = KFold(5, shuffle=True)
    try:
        loss = log_loss(y, model_predict(lr, depth))
    except Exception:
        return 0.0
    trial.report(loss, 0)
    return loss


study = optuna.create_study(direction="maximize", pruner=optuna.pruners.MedianPruner())
study.optimize(objective, n_trials=50)
