"""Public helpers for NMF, clustering, figures, and artifact export."""

from .artifacts import export_results, summarize_group_results, summarize_subject_results
from .clustering import cluster_feature_group, cluster_intra_subject
from .concatenated import build_concatenated_feature_rows, split_and_average_h_by_trial
from .figures import save_group_cluster_figure, save_subject_cluster_figure, save_trial_nmf_figure
from .methods import normalize_analysis_mode, resolve_analysis_modes
from .nmf import extract_trial_features

__all__ = [
    "build_concatenated_feature_rows",
    "cluster_feature_group",
    "cluster_intra_subject",
    "export_results",
    "extract_trial_features",
    "normalize_analysis_mode",
    "resolve_analysis_modes",
    "save_group_cluster_figure",
    "save_subject_cluster_figure",
    "save_trial_nmf_figure",
    "split_and_average_h_by_trial",
    "summarize_group_results",
    "summarize_subject_results",
]
