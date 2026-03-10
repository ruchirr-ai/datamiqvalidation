"""Compatibility Engine for BigQuery to Redshift Migration"""
import logging, json, os
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

BQ_TO_REDSHIFT_TYPE_MAP: Dict[str, tuple] = {
    "INT64": ("BIGINT", "full", "Direct mapping"),
    "INTEGER": ("BIGINT", "full", "Direct mapping"),
    "INT": ("BIGINT", "full", "Direct mapping"),
    "SMALLINT": ("SMALLINT", "full", "Direct mapping"),
    "TINYINT": ("SMALLINT", "full", "Direct mapping"),
    "BYTEINT": ("SMALLINT", "full", "Direct mapping"),
    "BIGINT": ("BIGINT", "full", "Direct mapping"),
    "FLOAT64": ("DOUBLE PRECISION", "full", "Direct mapping"),
    "FLOAT": ("DOUBLE PRECISION", "full", "Direct mapping"),
    "NUMERIC": ("DECIMAL(38,9)", "full", "BQ NUMERIC 38,9. Redshift up to 38."),
    "BIGNUMERIC": ("DECIMAL(38,18)", "lossy", "BQ 76.76 digits. Redshift max 38."),
    "DECIMAL": ("DECIMAL(38,9)", "full", "Direct mapping"),
    "BIGDECIMAL": ("DECIMAL(38,18)", "lossy", "Precision loss beyond 38 digits."),
    "BOOL": ("BOOLEAN", "full", "Direct mapping"),
    "BOOLEAN": ("BOOLEAN", "full", "Direct mapping"),
    "STRING": ("VARCHAR(65535)", "partial", "BQ unlimited. Redshift max 65535."),
    "BYTES": ("VARCHAR(65535)", "partial", "Binary as hex string."),
    "DATE": ("DATE", "full", "Direct mapping"),
    "TIME": ("TIME", "full", "Direct mapping"),
    "DATETIME": ("TIMESTAMP", "partial", "BQ no tz. Redshift TIMESTAMP."),
    "TIMESTAMP": ("TIMESTAMPTZ", "partial", "BQ UTC. Redshift TIMESTAMPTZ."),
    "STRUCT": ("SUPER", "partial", "Requires SUPER + PartiQL."),
    "RECORD": ("SUPER", "partial", "Same as STRUCT."),
    "ARRAY": ("SUPER", "partial", "Requires PartiQL."),
    "JSON": ("SUPER", "partial", "Maps to SUPER."),
    "GEOGRAPHY": ("GEOMETRY", "partial", "Spherical vs planar."),
    "INTERVAL": ("VARCHAR(100)", "lossy", "No native INTERVAL."),
    "RANGE": ("VARCHAR(255)", "lossy", "No native RANGE."),
}

class CompatibilityEngine:
    def run_compatibility_check(self, assessment_id: int, db) -> Dict[str, Any]:
        from repositories.assessment_repository import AssessmentRepository
        repo = AssessmentRepository(db)
        a = repo.get_by_id(assessment_id)
        if not a:
            raise ValueError(f"Assessment {assessment_id} not found")
        tables = repo.get_tables(assessment_id)
        columns = repo.get_columns(assessment_id)
        views = repo.get_views(assessment_id)
        routines = repo.get_routines(assessment_id)
        ml_models = repo.get_ml_models(assessment_id)
        security = repo.get_security_policies(assessment_id)
        sharded = repo.get_sharded_tables(assessment_id)
        td = [self._orm_to_dict(t) for t in tables]
        cd = [self._orm_to_dict(c) for c in columns]
        vd = [self._orm_to_dict(v) for v in views]
        rd = [self._orm_to_dict(r) for r in routines]
        mld = [self._orm_to_dict(m) for m in ml_models]
        sd = [self._orm_to_dict(s) for s in security]
        shd = [self._orm_to_dict(s) for s in sharded]
        dta = self._analyze_data_types(td, cd)
        fg = self._analyze_feature_gaps(vd, rd, mld, sd, shd, td, cd)
        sql = self._analyze_sql_syntax(rd, vd)
        score = self._calculate_score(dta, fg, sql)
        report = {
            "assessment_id": assessment_id, "assessment_name": a.name,
            "overall_score": score["overall"], "score_breakdown": score,
            "summary": {"total_tables": len(td), "total_columns": len(cd),
                "total_views": len(vd), "total_routines": len(rd),
                "total_ml_models": len(mld), "total_security_policies": len(sd),
                "total_sharded_tables": len(shd)},
            "data_type_analysis": dta, "feature_gaps": fg, "sql_syntax_issues": sql,
        }
        try:
            llm = self._enhance_with_llm(report)
            if llm:
                report["llm_insights"] = llm
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
            report["llm_insights"] = None
        return report

    def _analyze_data_types(self, tables, columns):
        results, stats = [], {"full": 0, "partial": 0, "lossy": 0, "unsupported": 0, "unknown": 0}
        tbl = {t.get("id"): f"{t.get('dataset_name','')}.{t.get('table_name','')}" for t in tables}
        for col in columns:
            bq = (col.get("data_type") or "").upper().split("<")[0].split("(")[0].strip()
            tn = tbl.get(col.get("table_id"), "unknown")
            if bq in BQ_TO_REDSHIFT_TYPE_MAP:
                rs, compat, notes = BQ_TO_REDSHIFT_TYPE_MAP[bq]
            else:
                rs, compat, notes = ("VARCHAR(65535)", "unknown", f"Unmapped type '{bq}'.")
            stats[compat] = stats.get(compat, 0) + 1
            results.append({"table_name": tn, "column_name": col.get("column_name"),
                "bq_type": col.get("data_type"), "redshift_type": rs,
                "compatibility": compat, "notes": notes})
        total = len(columns) or 1
        return {"mappings": results, "stats": stats,
            "compatibility_pct": round((stats["full"] / total) * 100, 1),
            "total_columns": len(columns)}

    def _analyze_feature_gaps(self, views, routines, ml_models, security, sharded, tables, columns):
        gaps = []
        if ml_models:
            gaps.append({"category": "ML Models (BQML)", "severity": "high", "count": len(ml_models),
                "description": f"{len(ml_models)} BQML model(s). No native ML in Redshift.",
                "items": [m.get("model_name", "") for m in ml_models],
                "recommendation": "Export and retrain using Amazon SageMaker."})
        js = [r for r in routines if (r.get("external_language") or "").upper() == "JAVASCRIPT"]
        if js:
            gaps.append({"category": "JavaScript UDFs", "severity": "high", "count": len(js),
                "description": f"{len(js)} JS UDF(s). Redshift supports Python/SQL only.",
                "items": [r.get("routine_name", "") for r in js],
                "recommendation": "Rewrite in Python (plpythonu) or SQL."})
        sp = [r for r in routines if (r.get("external_language") or "").upper() in ("PYTHON", "SPARK") and r.get("routine_type", "").upper() == "PROCEDURE"]
        if sp:
            gaps.append({"category": "Spark Procedures", "severity": "medium", "count": len(sp),
                "description": f"{len(sp)} Spark/Python procedure(s). Redshift uses PL/pgSQL.",
                "items": [r.get("routine_name", "") for r in sp],
                "recommendation": "Rewrite in PL/pgSQL or move to AWS Glue/EMR."})
        mv = [v for v in views if (v.get("view_type") or "").upper() == "MATERIALIZED_VIEW"]
        if mv:
            gaps.append({"category": "Materialized Views", "severity": "low", "count": len(mv),
                "description": f"{len(mv)} materialized view(s). Different refresh semantics.",
                "items": [v.get("view_name", "") for v in mv],
                "recommendation": "Recreate as Redshift MVs with auto-refresh."})
        rls = [s for s in security if (s.get("security_type") or "").upper() == "RLS"]
        cls = [s for s in security if (s.get("security_type") or "").upper() == "CLS"]
        if rls:
            gaps.append({"category": "Row-Level Security", "severity": "medium", "count": len(rls),
                "description": f"{len(rls)} RLS policies. Syntax differs in Redshift.",
                "items": [s.get("policy_name", "") for s in rls],
                "recommendation": "Recreate using Redshift CREATE RLS POLICY."})
        if cls:
            gaps.append({"category": "Column-Level Security", "severity": "medium", "count": len(cls),
                "description": f"{len(cls)} CLS policies. Use GRANT/REVOKE at column level.",
                "items": [s.get("policy_name", "") for s in cls],
                "recommendation": "Use Redshift column-level GRANT/REVOKE."})
        if sharded:
            gaps.append({"category": "Sharded Tables", "severity": "medium", "count": len(sharded),
                "description": f"{len(sharded)} sharded table group(s).",
                "items": [s.get("shard_group", "") for s in sharded],
                "recommendation": "Consolidate into single tables with sort keys."})
        cx = [c for c in columns if (c.get("data_type") or "").upper().split("<")[0].split("(")[0].strip() in ("STRUCT", "RECORD", "ARRAY")]
        if cx:
            gaps.append({"category": "Complex/Nested Types", "severity": "medium", "count": len(cx),
                "description": f"{len(cx)} STRUCT/RECORD/ARRAY column(s).",
                "items": list(set(c.get("data_type", "") for c in cx))[:10],
                "recommendation": "Flatten where possible. Use SUPER + PartiQL."})
        geo = [c for c in columns if (c.get("data_type") or "").upper().startswith("GEOGRAPHY")]
        if geo:
            gaps.append({"category": "Geospatial Data", "severity": "low", "count": len(geo),
                "description": f"{len(geo)} GEOGRAPHY column(s).",
                "items": [c.get("column_name", "") for c in geo][:10],
                "recommendation": "Convert to Redshift GEOMETRY."})
        pt = [t for t in tables if t.get("partitioning_columns")]
        if pt:
            gaps.append({"category": "Partitioned Tables", "severity": "low", "count": len(pt),
                "description": f"{len(pt)} partitioned table(s). Use sort keys instead.",
                "items": [f"{t.get('dataset_name','')}.{t.get('table_name','')}" for t in pt][:10],
                "recommendation": "Map BQ partition columns to Redshift SORTKEY."})
        return gaps

    def _analyze_sql_syntax(self, routines, views):
        issues = []
        patterns = [
            ("SAFE_DIVIDE", "high", "Use CASE WHEN or NULLIF"),
            ("SAFE_CAST", "medium", "Use TRY_CAST"),
            ("PARSE_DATE", "medium", "Use TO_DATE"),
            ("PARSE_TIMESTAMP", "medium", "Use TO_TIMESTAMP"),
            ("FORMAT_DATE", "medium", "Use TO_CHAR"),
            ("FORMAT_TIMESTAMP", "medium", "Use TO_CHAR"),
            ("UNNEST", "high", "Use PartiQL or lateral flatten"),
            ("ARRAY_AGG", "medium", "Use LISTAGG"),
            ("STRUCT(", "high", "No STRUCT constructor. Use SUPER."),
            ("GENERATE_ARRAY", "medium", "Use recursive CTE or generate_series"),
            ("GENERATE_DATE_ARRAY", "medium", "Use generate_series"),
            ("IF(", "low", "Use CASE WHEN"),
            ("IFNULL", "low", "Use COALESCE or NVL"),
            ("COUNTIF", "medium", "Use COUNT(CASE WHEN ...)"),
            ("ANY_VALUE", "low", "Use MIN or MAX"),
            ("APPROX_COUNT_DISTINCT", "low", "Use APPROXIMATE COUNT(DISTINCT)"),
            ("FARM_FINGERPRINT", "medium", "Use MD5 or SHA2"),
            ("ML.PREDICT", "high", "Use Redshift ML or SageMaker"),
            ("ML.EVALUATE", "high", "Use SageMaker"),
            ("QUALIFY", "high", "Use subquery with window function"),
            ("PIVOT", "medium", "Use conditional aggregation"),
            ("UNPIVOT", "medium", "Use UNION ALL"),
            ("EXCEPT(", "medium", "List columns explicitly"),
        ]
        all_sql = []
        for r in routines:
            d = r.get("definition") or ""
            if d: all_sql.append(("routine", r.get("routine_name", ""), d))
        for v in views:
            d = v.get("view_definition") or ""
            if d: all_sql.append(("view", v.get("view_name", ""), d))
        for pat, sev, fix in patterns:
            affected = [f"{t}: {n}" for t, n, s in all_sql if pat.upper() in s.upper()]
            if affected:
                issues.append({"pattern": pat, "severity": sev, "fix": fix,
                    "affected_count": len(affected), "affected_items": affected[:10]})
        return issues

    def _calculate_score(self, dta, fg, sql):
        stats = dta.get("stats", {})
        total = dta.get("total_columns", 0) or 1
        dt = round(((stats.get("full", 0) * 1.0 + stats.get("partial", 0) * 0.7 + stats.get("lossy", 0) * 0.3) / total) * 100, 1)
        gp = sum(g.get("count", 1) * (5 if g.get("severity") == "high" else 2 if g.get("severity") == "medium" else 0.5) for g in fg)
        fg_s = max(0, round(100 - gp, 1))
        sp = sum(i.get("affected_count", 1) * (4 if i.get("severity") == "high" else 2 if i.get("severity") == "medium" else 0.5) for i in sql)
        sql_s = max(0, round(100 - sp, 1))
        overall = round(dt * 0.4 + fg_s * 0.35 + sql_s * 0.25, 1)
        return {"overall": min(100, max(0, overall)), "data_types": dt, "feature_gaps": fg_s, "sql_syntax": sql_s}

    def _enhance_with_llm(self, report):
        use_bedrock = os.getenv("CLAUDE_USE_BEDROCK", "false").lower() == "true"
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not use_bedrock and not api_key:
            return None
        summary = {
            "overall_score": report.get("overall_score"),
            "score_breakdown": report.get("score_breakdown"),
            "summary": report.get("summary"),
            "data_type_stats": report.get("data_type_analysis", {}).get("stats"),
            "feature_gaps": [{"category": g["category"], "severity": g["severity"],
                "count": g["count"], "description": g["description"]} for g in report.get("feature_gaps", [])],
            "sql_syntax_issues": [{"pattern": i["pattern"], "severity": i["severity"],
                "affected_count": i["affected_count"]} for i in report.get("sql_syntax_issues", [])],
        }
        prompt = "You are a database migration strategist. Be extremely concise.\n"
        prompt += "Given this BigQuery to Redshift compatibility report, provide STRATEGIC insights.\n"
        prompt += "DO NOT repeat feature gaps or data type issues - those are already shown separately.\n"
        prompt += "Focus on: timeline, team planning, cost, testing strategy, rollback plan.\n\n"
        prompt += "Respond in JSON with these fields:\n"
        prompt += "- executive_summary: 1 sentence strategic overview\n"
        prompt += "- effort_level: Low/Medium/High\n"
        prompt += "- migration_approach: 1 short sentence (phased/big-bang/parallel)\n"
        prompt += "- estimated_timeline: e.g. '2-3 weeks'\n"
        prompt += "- team_requirements: array of {role: string, reason: string}, max 3\n"
        prompt += "- testing_strategy: array of short steps, max 4 items, 8 words each\n"
        prompt += "- rollback_plan: 1 short sentence\n"
        prompt += "- cost_considerations: array of short items, max 3, 8 words each\n\n"
        prompt += f"Report: {json.dumps(summary)}\n\n"
        prompt += "IMPORTANT: Keep ALL text extremely short. Do NOT mention specific feature gaps or data type issues."
        try:
            if use_bedrock:
                return self._call_bedrock(prompt)
            return self._call_anthropic(prompt, api_key)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _call_bedrock(self, prompt):
        import boto3
        from botocore.config import Config
        region = os.getenv("AWS_REGION", "us-east-1")
        model_id = os.getenv("COMPAT_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
        config = Config(read_timeout=30, connect_timeout=10, retries={"max_attempts": 1})
        client = boto3.client("bedrock-runtime", region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=config)
        body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 512,
            "temperature": 0.1, "messages": [{"role": "user", "content": prompt}]})
        resp = client.invoke_model(modelId=model_id, contentType="application/json",
            accept="application/json", body=body)
        result = json.loads(resp["body"].read())
        text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
        return self._parse_llm_json(text)

    def _call_anthropic(self, prompt, api_key):
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(model="claude-3-5-haiku-20241022",
            max_tokens=512, temperature=0.1, messages=[{"role": "user", "content": prompt}])
        if resp.content:
            return self._parse_llm_json(resp.content[0].text)
        return None

    def _parse_llm_json(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for marker in ["```json", "```"]:
            if marker in text:
                start = text.index(marker) + len(marker)
                end = text.index("```", start)
                try:
                    return json.loads(text[start:end].strip())
                except Exception:
                    pass
        return None

    @staticmethod
    def _orm_to_dict(obj):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
