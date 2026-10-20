"""Known-answer chronological evaluation and the authenticated upload boundary."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from ml.audit import band_outcomes, chronological_split, history_backtest
from ml.ingest import load_export
from ml.labeling import add_labels

FIXTURE = Path(__file__).parent / 'fixtures' / '1c_export_cp1251.csv'


def history():
    order = pd.date_range('2024-01-01', periods=100, freq='7D')
    late = np.arange(100) % 2
    return pd.DataFrame({'supplier_id': ['A'] * 100,
                         'material_type': ['ready_mix_concrete'] * 100,
                         'route_type': ['unknown'] * 100,
                         'quantity': np.where(late, 100, 10),
                         'order_date': order,
                         'promised_date': order + pd.Timedelta(days=1),
                         'actual_date': order + pd.to_timedelta(1 + 2 * late, unit='D')})


def upload(client, raw=None, **kwargs):
    return client.post('/audit/history', files={'file': ('history.csv', raw if raw is not None else FIXTURE.read_bytes(), 'text/csv')}, **kwargs)


def test_iso_and_mixed_export_dates_preserve_all_rows():
    source = history()
    raw = source.to_csv(index=False).encode()
    frame, quality = load_export(raw)
    assert quality.rows_kept == 100 and quality.bad_dates == 0
    pd.testing.assert_series_equal(frame.order_date, source.order_date, check_dtype=False)
    mixed = source.head(3).copy()
    for column in ('order_date', 'promised_date', 'actual_date'):
        mixed[column] = [source.loc[0, column].strftime('%Y-%m-%d'),
                         source.loc[1, column].strftime('%d.%m.%Y'),
                         source.loc[2, column].strftime('%Y-%m-%d')]
    frame, _ = load_export(mixed.to_csv(index=False).encode())
    assert frame.order_date.tolist() == source.head(3).order_date.tolist()


def test_nonfinite_quantities_and_duplicate_aliases_are_rejected():
    source = history().head(5).copy()
    source['quantity'] = ['inf', '-inf', '0', '-5', '10']
    frame, quality = load_export(source.to_csv(index=False).encode())
    assert len(frame) == 1 and quality.bad_quantity == 4
    source['Поставщик'] = source.supplier_id
    with pytest.raises(ValueError, match='Несколько столбцов'):
        load_export(source.to_csv(index=False).encode())


def test_russian_material_grace_matches_canonical_rules_and_reports_unknowns():
    from ml.labeling import LabelConfig, canonical_material_type
    frame = history().head(7).copy()
    frame['material_type'] = [' БЕТОН ', 'Цемент', 'Арматура', 'Утеплитель', 'Кирпич', 'Плитка', 'Арматура A500']
    frame['actual_date'] = frame.promised_date + pd.to_timedelta([1, 1, 2, 2, 3, 3, 2], unit='D')
    parsed, quality = load_export(frame.to_csv(index=False).encode())
    assert add_labels(parsed).is_late.tolist() == [1, 0, 0, 0, 0, 0, 1]
    assert canonical_material_type(' БЕТОН ') == 'ready_mix_concrete'
    assert canonical_material_type('Арматура A500') == 'арматура a500'
    assert parsed.material_type.iloc[2] == 'Арматура'
    assert quality.material_grace_defaulted == 1
    assert 'default material grace' in quality.summary()
    assert LabelConfig(grace_days_by_material={'Арматура': 5}).grace_for('Арматура') == 5


def test_chronological_split_known_answer():
    source = history()
    before = source.copy(deep=True)
    train, test, info = chronological_split(source)
    assert (len(train), len(test)) == (70, 30)
    assert train.order_date.max() < test.order_date.min()
    assert train.actual_date.max() < test.order_date.min()
    assert info['purged_train_rows'] == info['excluded_chronology'] == 0
    pd.testing.assert_frame_equal(source, before)


def test_split_purges_future_completions_and_keeps_date_ties_together():
    source = history()
    source.loc[69, ['order_date', 'promised_date', 'actual_date']] = source.loc[70, ['order_date', 'promised_date', 'actual_date']].values
    source.loc[0, 'actual_date'] = source.loc[70, 'order_date'] + pd.Timedelta(days=1)
    train, test, info = chronological_split(source)
    assert (len(train), len(test), info['purged_train_rows']) == (68, 31, 1)
    assert train.actual_date.max() < test.order_date.min()
    assert not set(train.order_date) & set(test.order_date)
    source.loc[1, 'promised_date'] = source.loc[1, 'order_date'] - pd.Timedelta(days=1)
    assert chronological_split(source)[2]['excluded_chronology'] == 1


def test_backtest_known_metrics():
    result = history_backtest(history())
    assert result['status'] == 'evaluated'
    assert (result['train_rows'], result['test_rows']) == (70, 30)
    assert result['model_average_precision'] == pytest.approx(1.0)
    assert result['baseline_average_precision'] == pytest.approx(0.5)
    assert result['lift'] == pytest.approx(0.5) and result['beats_baseline'] is True
    assert result['risk_bands']['red']['late_rate'] == 1
    assert result['risk_bands']['green']['late_rate'] == 0
    assert sum(row['deliveries'] for row in result['risk_bands'].values()) == 30


def test_held_out_outcomes_never_enter_training_or_features(monkeypatch):
    import ml.audit as audit
    original = audit.make_model
    matrices = []

    class RecordingModel:
        def fit(self, X, y):
            matrices.append((X.copy(), y.copy()))
            self.model = original(seed=0).fit(X, y)
            return self

        def predict_proba(self, X):
            matrices.append(X.copy())
            return self.model.predict_proba(X)

    monkeypatch.setattr(audit, 'make_model', lambda seed: RecordingModel())
    frame = history()
    history_backtest(frame)
    frame.loc[70:, 'actual_date'] = frame.loc[70:, 'promised_date'] + pd.to_timedelta(np.where(np.arange(30) % 2, 0, 2), unit='D')
    history_backtest(frame)
    np.testing.assert_array_equal(matrices[0][0], matrices[2][0])
    np.testing.assert_array_equal(matrices[0][1], matrices[2][1])
    np.testing.assert_array_equal(matrices[1], matrices[3])
    # A new material/supplier in the held-out period cannot expand training vocabulary.
    frame.loc[70:, 'material_type'] = 'never-trained'
    frame.loc[70:, 'supplier_id'] = 'new'
    history_backtest(frame)
    assert matrices[5].shape == matrices[1].shape
    assert np.isfinite(matrices[5]).all()


def test_model_losing_to_baseline_releases_no_risk_bands(monkeypatch):
    import ml.audit as audit

    class ConstantModel:
        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            return np.tile([0.5, 0.5], (len(X), 1))

    frame = history()
    frame['supplier_id'] = np.where(np.arange(100) % 2, 'late-supplier', 'on-time-supplier')
    monkeypatch.setattr(audit, 'make_model', lambda seed: ConstantModel())
    result = history_backtest(frame)
    assert result['model_average_precision'] == 0.5
    assert result['baseline_average_precision'] == 1
    assert result['beats_baseline'] is False and result['risk_bands'] == {}


def test_insufficient_history_does_not_invent_accuracy():
    for frame in [history().head(0), history().head(1), history().head(8),
                  history().assign(actual_date=history().promised_date),
                  history().assign(order_date=pd.Timestamp('2024-01-01'))]:
        result = history_backtest(frame)
        assert result['status'] == 'insufficient_data' and result['reason']
        assert result['model_average_precision'] is None
        assert result['beats_baseline'] is None and result['risk_bands'] == {}
    assert chronological_split(history().head(1))[1].empty


def test_band_boundaries_known_answer():
    result = band_outcomes(np.array([0, 1, 1, 0]), np.array([0.33, 0.66, 0.6601, 0.9]))
    assert result == {'green': {'deliveries': 1, 'late_rate': 0},
                      'yellow': {'deliveries': 1, 'late_rate': 1},
                      'red': {'deliveries': 2, 'late_rate': 0.5}}
    assert band_outcomes(np.array([1]), np.array([0.9]))['green']['late_rate'] is None


def test_fixture_api_returns_three_blocks_without_persistence(api_client, temp_db, tmp_path, monkeypatch):
    archive = tmp_path / 'archive'
    monkeypatch.setenv('SITEPULSE_AUDIT_DIR', str(archive))
    tables = temp_db['database'].Base.metadata.tables
    with temp_db['Session']() as db:
        before = {name: db.scalar(select(func.count()).select_from(table)) for name, table in tables.items()}
    result = upload(api_client, data={'synthetic': 'true'})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['data_source'] == 'synthetic_upload'
    assert data['quality']['rows_total'] == 12 and data['quality']['rows_kept'] == 8
    assert data['quality']['rows_dropped'] == 4
    assert sum(s['deliveries'] for s in data['scorecard']) == 8
    assert data['material_breakdown'] and data['backtest']['status'] == 'insufficient_data'
    assert data['saved'] is False and data['audit_id'] is None and not archive.exists()
    assert 'NaN' not in result.text and 'test-admin-key' not in result.text
    with temp_db['Session']() as db:
        after = {name: db.scalar(select(func.count()).select_from(table)) for name, table in tables.items()}
    assert after == before


def test_evaluated_upload_never_touches_serving_artifact(api_client, monkeypatch):
    import api.model_store
    import ml.predict
    import ml.train
    artifact = ml.train.ARTIFACT_PATH
    before = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.exists() else None

    def forbidden(*args, **kwargs):
        pytest.fail('Audit accessed the serving model')

    monkeypatch.setattr(api.model_store, 'get_artifact', forbidden)
    monkeypatch.setattr(ml.predict, 'load_artifact', forbidden)
    monkeypatch.setattr(ml.train, 'fit_and_save', forbidden)
    result = upload(api_client, history().to_csv(index=False).encode())
    assert result.status_code == 200, result.text
    assert result.json()['backtest']['status'] == 'evaluated'
    assert result.json()['data_source'] == 'uploaded_unverified'
    after = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.exists() else None
    assert before == after


def test_archive_is_explicit_and_uses_server_generated_names(api_client, monkeypatch, tmp_path):
    monkeypatch.delenv('SITEPULSE_AUDIT_DIR', raising=False)
    assert upload(api_client, params={'save': 'true'}).status_code == 409
    archive = tmp_path / 'archive'
    monkeypatch.setenv('SITEPULSE_AUDIT_DIR', str(archive))
    response = api_client.post('/audit/history?save=true', files={'file': ('../../escape.csv', FIXTURE.read_bytes(), 'text/csv')})
    assert response.status_code == 200, response.text
    data = response.json()
    folder = archive / data['audit_id']
    assert data['saved'] is True and len(data['audit_id']) == 32
    assert set(p.name for p in folder.iterdir()) == {'deliveries.csv', 'report.json'}
    assert len(pd.read_csv(folder / 'deliveries.csv')) == 8
    assert json.loads((folder / 'report.json').read_text()) == data
    assert not (tmp_path / 'escape.csv').exists()


@pytest.mark.parametrize('raw', [b'', b'x,y\n1,2', b'just some text', b'\x00\x01\x02'])
def test_unusable_upload_is_422(api_client, raw):
    assert upload(api_client, raw).status_code == 422


def test_upload_limits_and_non_csv(api_client, monkeypatch):
    import api.routers.audit as audit
    response = api_client.post('/audit/history', files={'file': ('history.xlsx', b'not-xlsx')})
    assert response.status_code == 422
    monkeypatch.setattr(audit, 'MAX_UPLOAD_BYTES', 16)
    assert upload(api_client, b'a' * 17).status_code == 413
    monkeypatch.setattr(audit, 'MAX_UPLOAD_BYTES', 5 * 1024 * 1024)
    monkeypatch.setattr(audit, 'MAX_AUDIT_ROWS', 1)
    assert upload(api_client).status_code == 413


def test_audit_requires_admin_and_releases_busy_lock(api_client, monkeypatch):
    import api.routers.audit as audit
    assert upload(api_client, headers={'X-API-Key': 'wrong'}).status_code == 401
    monkeypatch.delenv('SITEPULSE_ADMIN_KEY')
    assert upload(api_client).status_code == 503
    monkeypatch.setenv('SITEPULSE_ADMIN_KEY', 'test-admin-key')
    audit._audit_lock.acquire()
    try:
        assert upload(api_client).status_code == 429
    finally:
        audit._audit_lock.release()
    assert upload(api_client, b'bad file').status_code == 422
    assert upload(api_client).status_code == 200


def test_archive_storage_error_is_503(api_client, monkeypatch, tmp_path):
    file = tmp_path / 'not-a-directory'
    file.write_text('occupied')
    monkeypatch.setenv('SITEPULSE_AUDIT_DIR', str(file))
    assert upload(api_client, params={'save': 'true'}).status_code == 503
    assert file.read_text() == 'occupied'
