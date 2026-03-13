import React, { createContext, useContext, useState, ReactNode } from 'react';

export type LanguageCode = 'en' | 'ko' | 'zh' | 'ja' | 'fr' | 'es' | 'de' | 'pt' | 'hi';

export interface LanguageOption {
  code: LanguageCode;
  label: string;       // Native name
  labelEn: string;     // English name
  flag: string;        // Emoji flag
}

export const LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English', labelEn: 'English', flag: '🇺🇸' },
  { code: 'ko', label: '한국어', labelEn: 'Korean', flag: '🇰🇷' },
  { code: 'zh', label: '中文', labelEn: 'Chinese', flag: '🇨🇳' },
  { code: 'ja', label: '日本語', labelEn: 'Japanese', flag: '🇯🇵' },
  { code: 'fr', label: 'Français', labelEn: 'French', flag: '🇫🇷' },
  { code: 'es', label: 'Español', labelEn: 'Spanish', flag: '🇪🇸' },
  { code: 'de', label: 'Deutsch', labelEn: 'German', flag: '🇩🇪' },
  { code: 'pt', label: 'Português', labelEn: 'Portuguese', flag: '🇧🇷' },
  { code: 'hi', label: 'हिन्दी', labelEn: 'Hindi', flag: '🇮🇳' },
];

// Translation keys — add more as needed
type TranslationKeys = {
  // Sidebar nav
  'nav.dashboard': string;
  'nav.workspaces': string;
  'nav.connections': string;
  'nav.assessments': string;
  'nav.migrations': string;
  'nav.jobs': string;
  'nav.converter': string;
  'nav.validations': string;
  'nav.monitoring': string;
  'nav.admin': string;
  // Sidebar sub-items
  'nav.schemaAnalysis': string;
  'nav.compatibilityCheck': string;
  'nav.assessmentReports': string;
  'nav.dataProfiling': string;
  'nav.running': string;
  'nav.queued': string;
  'nav.history': string;
  'nav.quickConvert': string;
  'nav.batch': string;
  'nav.queryHistory': string;
  'nav.copyHistory': string;
  'nav.taskHistory': string;
  'nav.dynamicTables': string;
  'nav.governance': string;
  // Sidebar footer
  'sidebar.darkMode': string;
  'sidebar.lightMode': string;
  'sidebar.language': string;
  'sidebar.myProfile': string;
  'sidebar.support': string;
  'sidebar.documentation': string;
  'sidebar.privacyNotice': string;
  'sidebar.signOut': string;
  // Assessments page
  'assessments.title': string;
  'assessments.new': string;
  'assessments.search': string;
  'assessments.name': string;
  'assessments.status': string;
  'assessments.datasets': string;
  'assessments.tables': string;
  'assessments.totalSize': string;
  'assessments.startedAt': string;
  'assessments.completedAt': string;
  'assessments.run': string;
  'assessments.viewLogs': string;
  'assessments.viewReport': string;
  'assessments.downloadReport': string;
  'assessments.edit': string;
  'assessments.delete': string;
  'assessments.deleteConfirm': string;
  'assessments.deleteConfirmMsg': string;
  'assessments.cancel': string;
  'assessments.noAssessments': string;
  'assessments.noAssessmentsDesc': string;
  'assessments.createFirst': string;
  'assessments.loading': string;
  'assessments.started': string;
  'assessments.completed': string;
  'assessments.failed': string;
  'assessments.pending': string;
  'assessments.rowsPerPage': string;
  'assessments.showing': string;
  // Common
  'common.of': string;
  'common.retry': string;
};

type Translations = Record<LanguageCode, TranslationKeys>;

const translations: Translations = {
  en: {
    'nav.dashboard': 'Dashboard',
    'nav.workspaces': 'Workspaces',
    'nav.connections': 'Connections',
    'nav.assessments': 'Assessments',
    'nav.migrations': 'Migrations',
    'nav.jobs': 'Jobs',
    'nav.converter': 'Code Converter',
    'nav.validations': 'Data Validation',
    'nav.monitoring': 'Monitoring',
    'nav.admin': 'Admin',
    'nav.schemaAnalysis': 'Schema Analysis',
    'nav.compatibilityCheck': 'Compatibility Check',
    'nav.assessmentReports': 'Assessment Reports',
    'nav.dataProfiling': 'Data Profiling',
    'nav.running': 'Running',
    'nav.queued': 'Queued',
    'nav.history': 'History',
    'nav.quickConvert': 'Quick Convert',
    'nav.batch': 'Batch',
    'nav.queryHistory': 'Query History',
    'nav.copyHistory': 'Copy History',
    'nav.taskHistory': 'Task History',
    'nav.dynamicTables': 'Dynamic Tables',
    'nav.governance': 'Governance',
    'sidebar.darkMode': 'Dark mode',
    'sidebar.lightMode': 'Light mode',
    'sidebar.language': 'Language',
    'sidebar.myProfile': 'My profile',
    'sidebar.support': 'Support',
    'sidebar.documentation': 'Documentation',
    'sidebar.privacyNotice': 'Privacy notice',
    'sidebar.signOut': 'Sign Out',
    'assessments.title': 'Assessments',
    'assessments.new': '+ New',
    'assessments.search': 'Search assessments',
    'assessments.name': 'NAME',
    'assessments.status': 'STATUS',
    'assessments.datasets': 'DATASETS',
    'assessments.tables': 'TABLES',
    'assessments.totalSize': 'TOTAL SIZE',
    'assessments.startedAt': 'STARTED AT',
    'assessments.completedAt': 'COMPLETED AT',
    'assessments.run': 'Run Assessment',
    'assessments.viewLogs': 'View Logs',
    'assessments.viewReport': 'View Report',
    'assessments.downloadReport': 'Download Report',
    'assessments.edit': 'Edit Assessment',
    'assessments.delete': 'Delete Assessment',
    'assessments.deleteConfirm': 'Delete Assessment',
    'assessments.deleteConfirmMsg': 'Are you sure you want to delete this assessment? This action cannot be undone.',
    'assessments.cancel': 'Cancel',
    'assessments.noAssessments': 'No assessments yet',
    'assessments.noAssessmentsDesc': 'Create your first BigQuery assessment to analyze your data',
    'assessments.createFirst': 'Create Your First Assessment',
    'assessments.loading': 'Loading assessments...',
    'assessments.started': 'Assessment started',
    'assessments.completed': 'Completed',
    'assessments.failed': 'Failed',
    'assessments.pending': 'Pending',
    'assessments.rowsPerPage': 'Rows per page:',
    'assessments.showing': 'Showing',
    'common.of': 'of',
    'common.retry': 'Retry',
  },
  ko: {
    'nav.dashboard': '대시보드', 'nav.workspaces': '워크스페이스', 'nav.connections': '연결',
    'nav.assessments': '평가', 'nav.migrations': '마이그레이션', 'nav.jobs': '작업',
    'nav.converter': '코드 변환기', 'nav.validations': '데이터 검증', 'nav.monitoring': '모니터링',
    'nav.admin': '관리자', 'nav.schemaAnalysis': '스키마 분석', 'nav.compatibilityCheck': '호환성 검사',
    'nav.assessmentReports': '평가 보고서', 'nav.dataProfiling': '데이터 프로파일링',
    'nav.running': '실행 중', 'nav.queued': '대기 중', 'nav.history': '기록',
    'nav.quickConvert': '빠른 변환', 'nav.batch': '일괄 처리',
    'nav.queryHistory': '쿼리 기록', 'nav.copyHistory': '복사 기록',
    'nav.taskHistory': '작업 기록', 'nav.dynamicTables': '동적 테이블', 'nav.governance': '거버넌스',
    'sidebar.darkMode': '다크 모드', 'sidebar.lightMode': '라이트 모드', 'sidebar.language': '언어',
    'sidebar.myProfile': '내 프로필', 'sidebar.support': '지원', 'sidebar.documentation': '문서',
    'sidebar.privacyNotice': '개인정보 보호', 'sidebar.signOut': '로그아웃',
    'assessments.title': '평가', 'assessments.new': '+ 새로 만들기', 'assessments.search': '평가 검색',
    'assessments.name': '이름', 'assessments.status': '상태', 'assessments.datasets': '데이터셋',
    'assessments.tables': '테이블', 'assessments.totalSize': '전체 크기',
    'assessments.startedAt': '시작 시간', 'assessments.completedAt': '완료 시간',
    'assessments.run': '평가 실행', 'assessments.viewLogs': '로그 보기',
    'assessments.viewReport': '보고서 보기', 'assessments.downloadReport': '보고서 다운로드',
    'assessments.edit': '평가 편집', 'assessments.delete': '평가 삭제',
    'assessments.deleteConfirm': '평가 삭제', 'assessments.deleteConfirmMsg': '이 평가를 삭제하시겠습니까? 이 작업은 취소할 수 없습니다.',
    'assessments.cancel': '취소', 'assessments.noAssessments': '아직 평가가 없습니다',
    'assessments.noAssessmentsDesc': '첫 번째 BigQuery 평가를 만들어 데이터를 분석하세요',
    'assessments.createFirst': '첫 번째 평가 만들기', 'assessments.loading': '평가 로딩 중...',
    'assessments.started': '평가 시작됨', 'assessments.completed': '완료됨',
    'assessments.failed': '실패', 'assessments.pending': '대기 중',
    'assessments.rowsPerPage': '페이지당 행:', 'assessments.showing': '표시 중',
    'common.of': '/', 'common.retry': '재시도',
  },
  zh: {
    'nav.dashboard': '仪表板', 'nav.workspaces': '工作区', 'nav.connections': '连接',
    'nav.assessments': '评估', 'nav.migrations': '迁移', 'nav.jobs': '任务',
    'nav.converter': '代码转换器', 'nav.validations': '数据验证', 'nav.monitoring': '监控',
    'nav.admin': '管理', 'nav.schemaAnalysis': '架构分析', 'nav.compatibilityCheck': '兼容性检查',
    'nav.assessmentReports': '评估报告', 'nav.dataProfiling': '数据分析',
    'nav.running': '运行中', 'nav.queued': '排队中', 'nav.history': '历史',
    'nav.quickConvert': '快速转换', 'nav.batch': '批量处理',
    'nav.queryHistory': '查询历史', 'nav.copyHistory': '复制历史',
    'nav.taskHistory': '任务历史', 'nav.dynamicTables': '动态表', 'nav.governance': '治理',
    'sidebar.darkMode': '深色模式', 'sidebar.lightMode': '浅色模式', 'sidebar.language': '语言',
    'sidebar.myProfile': '我的资料', 'sidebar.support': '支持', 'sidebar.documentation': '文档',
    'sidebar.privacyNotice': '隐私声明', 'sidebar.signOut': '退出登录',
    'assessments.title': '评估', 'assessments.new': '+ 新建', 'assessments.search': '搜索评估',
    'assessments.name': '名称', 'assessments.status': '状态', 'assessments.datasets': '数据集',
    'assessments.tables': '表', 'assessments.totalSize': '总大小',
    'assessments.startedAt': '开始时间', 'assessments.completedAt': '完成时间',
    'assessments.run': '运行评估', 'assessments.viewLogs': '查看日志',
    'assessments.viewReport': '查看报告', 'assessments.downloadReport': '下载报告',
    'assessments.edit': '编辑评估', 'assessments.delete': '删除评估',
    'assessments.deleteConfirm': '删除评估', 'assessments.deleteConfirmMsg': '确定要删除此评估吗？此操作无法撤消。',
    'assessments.cancel': '取消', 'assessments.noAssessments': '暂无评估',
    'assessments.noAssessmentsDesc': '创建您的第一个BigQuery评估来分析数据',
    'assessments.createFirst': '创建第一个评估', 'assessments.loading': '加载评估中...',
    'assessments.started': '评估已开始', 'assessments.completed': '已完成',
    'assessments.failed': '失败', 'assessments.pending': '待处理',
    'assessments.rowsPerPage': '每页行数:', 'assessments.showing': '显示',
    'common.of': '/', 'common.retry': '重试',
  },
  ja: {
    'nav.dashboard': 'ダッシュボード', 'nav.workspaces': 'ワークスペース', 'nav.connections': '接続',
    'nav.assessments': '評価', 'nav.migrations': '移行', 'nav.jobs': 'ジョブ',
    'nav.converter': 'コード変換', 'nav.validations': 'データ検証', 'nav.monitoring': 'モニタリング',
    'nav.admin': '管理', 'nav.schemaAnalysis': 'スキーマ分析', 'nav.compatibilityCheck': '互換性チェック',
    'nav.assessmentReports': '評価レポート', 'nav.dataProfiling': 'データプロファイリング',
    'nav.running': '実行中', 'nav.queued': 'キュー待ち', 'nav.history': '履歴',
    'nav.quickConvert': 'クイック変換', 'nav.batch': 'バッチ',
    'nav.queryHistory': 'クエリ履歴', 'nav.copyHistory': 'コピー履歴',
    'nav.taskHistory': 'タスク履歴', 'nav.dynamicTables': '動的テーブル', 'nav.governance': 'ガバナンス',
    'sidebar.darkMode': 'ダークモード', 'sidebar.lightMode': 'ライトモード', 'sidebar.language': '言語',
    'sidebar.myProfile': 'マイプロフィール', 'sidebar.support': 'サポート', 'sidebar.documentation': 'ドキュメント',
    'sidebar.privacyNotice': 'プライバシー', 'sidebar.signOut': 'サインアウト',
    'assessments.title': '評価', 'assessments.new': '+ 新規', 'assessments.search': '評価を検索',
    'assessments.name': '名前', 'assessments.status': 'ステータス', 'assessments.datasets': 'データセット',
    'assessments.tables': 'テーブル', 'assessments.totalSize': '合計サイズ',
    'assessments.startedAt': '開始時刻', 'assessments.completedAt': '完了時刻',
    'assessments.run': '評価を実行', 'assessments.viewLogs': 'ログを表示',
    'assessments.viewReport': 'レポートを表示', 'assessments.downloadReport': 'レポートをダウンロード',
    'assessments.edit': '評価を編集', 'assessments.delete': '評価を削除',
    'assessments.deleteConfirm': '評価を削除', 'assessments.deleteConfirmMsg': 'この評価を削除しますか？この操作は元に戻せません。',
    'assessments.cancel': 'キャンセル', 'assessments.noAssessments': '評価がありません',
    'assessments.noAssessmentsDesc': '最初のBigQuery評価を作成してデータを分析しましょう',
    'assessments.createFirst': '最初の評価を作成', 'assessments.loading': '評価を読み込み中...',
    'assessments.started': '評価を開始しました', 'assessments.completed': '完了',
    'assessments.failed': '失敗', 'assessments.pending': '保留中',
    'assessments.rowsPerPage': '表示行数:', 'assessments.showing': '表示中',
    'common.of': '/', 'common.retry': '再試行',
  },
  fr: {
    'nav.dashboard': 'Tableau de bord', 'nav.workspaces': 'Espaces de travail', 'nav.connections': 'Connexions',
    'nav.assessments': 'Évaluations', 'nav.migrations': 'Migrations', 'nav.jobs': 'Tâches',
    'nav.converter': 'Convertisseur', 'nav.validations': 'Validation', 'nav.monitoring': 'Surveillance',
    'nav.admin': 'Admin', 'nav.schemaAnalysis': 'Analyse de schéma', 'nav.compatibilityCheck': 'Vérification de compatibilité',
    'nav.assessmentReports': 'Rapports d\'évaluation', 'nav.dataProfiling': 'Profilage de données',
    'nav.running': 'En cours', 'nav.queued': 'En attente', 'nav.history': 'Historique',
    'nav.quickConvert': 'Conversion rapide', 'nav.batch': 'Lot',
    'nav.queryHistory': 'Historique des requêtes', 'nav.copyHistory': 'Historique des copies',
    'nav.taskHistory': 'Historique des tâches', 'nav.dynamicTables': 'Tables dynamiques', 'nav.governance': 'Gouvernance',
    'sidebar.darkMode': 'Mode sombre', 'sidebar.lightMode': 'Mode clair', 'sidebar.language': 'Langue',
    'sidebar.myProfile': 'Mon profil', 'sidebar.support': 'Support', 'sidebar.documentation': 'Documentation',
    'sidebar.privacyNotice': 'Confidentialité', 'sidebar.signOut': 'Déconnexion',
    'assessments.title': 'Évaluations', 'assessments.new': '+ Nouveau', 'assessments.search': 'Rechercher',
    'assessments.name': 'NOM', 'assessments.status': 'STATUT', 'assessments.datasets': 'JEUX DE DONNÉES',
    'assessments.tables': 'TABLES', 'assessments.totalSize': 'TAILLE TOTALE',
    'assessments.startedAt': 'DÉMARRÉ LE', 'assessments.completedAt': 'TERMINÉ LE',
    'assessments.run': 'Exécuter', 'assessments.viewLogs': 'Voir les logs',
    'assessments.viewReport': 'Voir le rapport', 'assessments.downloadReport': 'Télécharger',
    'assessments.edit': 'Modifier', 'assessments.delete': 'Supprimer',
    'assessments.deleteConfirm': 'Supprimer l\'évaluation', 'assessments.deleteConfirmMsg': 'Êtes-vous sûr de vouloir supprimer cette évaluation ? Cette action est irréversible.',
    'assessments.cancel': 'Annuler', 'assessments.noAssessments': 'Aucune évaluation',
    'assessments.noAssessmentsDesc': 'Créez votre première évaluation BigQuery',
    'assessments.createFirst': 'Créer une évaluation', 'assessments.loading': 'Chargement...',
    'assessments.started': 'Évaluation démarrée', 'assessments.completed': 'Terminé',
    'assessments.failed': 'Échoué', 'assessments.pending': 'En attente',
    'assessments.rowsPerPage': 'Lignes par page :', 'assessments.showing': 'Affichage',
    'common.of': 'sur', 'common.retry': 'Réessayer',
  },
  es: {
    'nav.dashboard': 'Panel', 'nav.workspaces': 'Espacios', 'nav.connections': 'Conexiones',
    'nav.assessments': 'Evaluaciones', 'nav.migrations': 'Migraciones', 'nav.jobs': 'Trabajos',
    'nav.converter': 'Convertidor', 'nav.validations': 'Validación', 'nav.monitoring': 'Monitoreo',
    'nav.admin': 'Admin', 'nav.schemaAnalysis': 'Análisis de esquema', 'nav.compatibilityCheck': 'Verificación de compatibilidad',
    'nav.assessmentReports': 'Informes de evaluación', 'nav.dataProfiling': 'Perfilado de datos',
    'nav.running': 'En ejecución', 'nav.queued': 'En cola', 'nav.history': 'Historial',
    'nav.quickConvert': 'Conversión rápida', 'nav.batch': 'Lote',
    'nav.queryHistory': 'Historial de consultas', 'nav.copyHistory': 'Historial de copias',
    'nav.taskHistory': 'Historial de tareas', 'nav.dynamicTables': 'Tablas dinámicas', 'nav.governance': 'Gobernanza',
    'sidebar.darkMode': 'Modo oscuro', 'sidebar.lightMode': 'Modo claro', 'sidebar.language': 'Idioma',
    'sidebar.myProfile': 'Mi perfil', 'sidebar.support': 'Soporte', 'sidebar.documentation': 'Documentación',
    'sidebar.privacyNotice': 'Privacidad', 'sidebar.signOut': 'Cerrar sesión',
    'assessments.title': 'Evaluaciones', 'assessments.new': '+ Nuevo', 'assessments.search': 'Buscar',
    'assessments.name': 'NOMBRE', 'assessments.status': 'ESTADO', 'assessments.datasets': 'CONJUNTOS',
    'assessments.tables': 'TABLAS', 'assessments.totalSize': 'TAMAÑO TOTAL',
    'assessments.startedAt': 'INICIADO', 'assessments.completedAt': 'COMPLETADO',
    'assessments.run': 'Ejecutar', 'assessments.viewLogs': 'Ver logs',
    'assessments.viewReport': 'Ver informe', 'assessments.downloadReport': 'Descargar',
    'assessments.edit': 'Editar', 'assessments.delete': 'Eliminar',
    'assessments.deleteConfirm': 'Eliminar evaluación', 'assessments.deleteConfirmMsg': '¿Está seguro de que desea eliminar esta evaluación? Esta acción no se puede deshacer.',
    'assessments.cancel': 'Cancelar', 'assessments.noAssessments': 'Sin evaluaciones',
    'assessments.noAssessmentsDesc': 'Cree su primera evaluación de BigQuery',
    'assessments.createFirst': 'Crear evaluación', 'assessments.loading': 'Cargando...',
    'assessments.started': 'Evaluación iniciada', 'assessments.completed': 'Completado',
    'assessments.failed': 'Fallido', 'assessments.pending': 'Pendiente',
    'assessments.rowsPerPage': 'Filas por página:', 'assessments.showing': 'Mostrando',
    'common.of': 'de', 'common.retry': 'Reintentar',
  },
  de: {
    'nav.dashboard': 'Dashboard', 'nav.workspaces': 'Arbeitsbereiche', 'nav.connections': 'Verbindungen',
    'nav.assessments': 'Bewertungen', 'nav.migrations': 'Migrationen', 'nav.jobs': 'Aufgaben',
    'nav.converter': 'Code-Konverter', 'nav.validations': 'Datenvalidierung', 'nav.monitoring': 'Überwachung',
    'nav.admin': 'Admin', 'nav.schemaAnalysis': 'Schema-Analyse', 'nav.compatibilityCheck': 'Kompatibilitätsprüfung',
    'nav.assessmentReports': 'Bewertungsberichte', 'nav.dataProfiling': 'Datenprofiling',
    'nav.running': 'Laufend', 'nav.queued': 'Warteschlange', 'nav.history': 'Verlauf',
    'nav.quickConvert': 'Schnellkonvertierung', 'nav.batch': 'Stapel',
    'nav.queryHistory': 'Abfrageverlauf', 'nav.copyHistory': 'Kopierverlauf',
    'nav.taskHistory': 'Aufgabenverlauf', 'nav.dynamicTables': 'Dynamische Tabellen', 'nav.governance': 'Governance',
    'sidebar.darkMode': 'Dunkelmodus', 'sidebar.lightMode': 'Hellmodus', 'sidebar.language': 'Sprache',
    'sidebar.myProfile': 'Mein Profil', 'sidebar.support': 'Support', 'sidebar.documentation': 'Dokumentation',
    'sidebar.privacyNotice': 'Datenschutz', 'sidebar.signOut': 'Abmelden',
    'assessments.title': 'Bewertungen', 'assessments.new': '+ Neu', 'assessments.search': 'Suchen',
    'assessments.name': 'NAME', 'assessments.status': 'STATUS', 'assessments.datasets': 'DATENSÄTZE',
    'assessments.tables': 'TABELLEN', 'assessments.totalSize': 'GESAMTGRÖSSE',
    'assessments.startedAt': 'GESTARTET', 'assessments.completedAt': 'ABGESCHLOSSEN',
    'assessments.run': 'Ausführen', 'assessments.viewLogs': 'Logs anzeigen',
    'assessments.viewReport': 'Bericht anzeigen', 'assessments.downloadReport': 'Herunterladen',
    'assessments.edit': 'Bearbeiten', 'assessments.delete': 'Löschen',
    'assessments.deleteConfirm': 'Bewertung löschen', 'assessments.deleteConfirmMsg': 'Möchten Sie diese Bewertung wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.',
    'assessments.cancel': 'Abbrechen', 'assessments.noAssessments': 'Keine Bewertungen',
    'assessments.noAssessmentsDesc': 'Erstellen Sie Ihre erste BigQuery-Bewertung',
    'assessments.createFirst': 'Erste Bewertung erstellen', 'assessments.loading': 'Laden...',
    'assessments.started': 'Bewertung gestartet', 'assessments.completed': 'Abgeschlossen',
    'assessments.failed': 'Fehlgeschlagen', 'assessments.pending': 'Ausstehend',
    'assessments.rowsPerPage': 'Zeilen pro Seite:', 'assessments.showing': 'Anzeige',
    'common.of': 'von', 'common.retry': 'Wiederholen',
  },
  pt: {
    'nav.dashboard': 'Painel', 'nav.workspaces': 'Espaços', 'nav.connections': 'Conexões',
    'nav.assessments': 'Avaliações', 'nav.migrations': 'Migrações', 'nav.jobs': 'Tarefas',
    'nav.converter': 'Conversor', 'nav.validations': 'Validação', 'nav.monitoring': 'Monitoramento',
    'nav.admin': 'Admin', 'nav.schemaAnalysis': 'Análise de esquema', 'nav.compatibilityCheck': 'Verificação de compatibilidade',
    'nav.assessmentReports': 'Relatórios', 'nav.dataProfiling': 'Perfil de dados',
    'nav.running': 'Em execução', 'nav.queued': 'Na fila', 'nav.history': 'Histórico',
    'nav.quickConvert': 'Conversão rápida', 'nav.batch': 'Lote',
    'nav.queryHistory': 'Histórico de consultas', 'nav.copyHistory': 'Histórico de cópias',
    'nav.taskHistory': 'Histórico de tarefas', 'nav.dynamicTables': 'Tabelas dinâmicas', 'nav.governance': 'Governança',
    'sidebar.darkMode': 'Modo escuro', 'sidebar.lightMode': 'Modo claro', 'sidebar.language': 'Idioma',
    'sidebar.myProfile': 'Meu perfil', 'sidebar.support': 'Suporte', 'sidebar.documentation': 'Documentação',
    'sidebar.privacyNotice': 'Privacidade', 'sidebar.signOut': 'Sair',
    'assessments.title': 'Avaliações', 'assessments.new': '+ Novo', 'assessments.search': 'Pesquisar',
    'assessments.name': 'NOME', 'assessments.status': 'STATUS', 'assessments.datasets': 'CONJUNTOS',
    'assessments.tables': 'TABELAS', 'assessments.totalSize': 'TAMANHO TOTAL',
    'assessments.startedAt': 'INICIADO', 'assessments.completedAt': 'CONCLUÍDO',
    'assessments.run': 'Executar', 'assessments.viewLogs': 'Ver logs',
    'assessments.viewReport': 'Ver relatório', 'assessments.downloadReport': 'Baixar',
    'assessments.edit': 'Editar', 'assessments.delete': 'Excluir',
    'assessments.deleteConfirm': 'Excluir avaliação', 'assessments.deleteConfirmMsg': 'Tem certeza de que deseja excluir esta avaliação? Esta ação não pode ser desfeita.',
    'assessments.cancel': 'Cancelar', 'assessments.noAssessments': 'Sem avaliações',
    'assessments.noAssessmentsDesc': 'Crie sua primeira avaliação BigQuery',
    'assessments.createFirst': 'Criar avaliação', 'assessments.loading': 'Carregando...',
    'assessments.started': 'Avaliação iniciada', 'assessments.completed': 'Concluído',
    'assessments.failed': 'Falhou', 'assessments.pending': 'Pendente',
    'assessments.rowsPerPage': 'Linhas por página:', 'assessments.showing': 'Mostrando',
    'common.of': 'de', 'common.retry': 'Tentar novamente',
  },
  hi: {
    'nav.dashboard': 'डैशबोर्ड', 'nav.workspaces': 'वर्कस्पेस', 'nav.connections': 'कनेक्शन',
    'nav.assessments': 'मूल्यांकन', 'nav.migrations': 'माइग्रेशन', 'nav.jobs': 'कार्य',
    'nav.converter': 'कोड कनवर्टर', 'nav.validations': 'डेटा सत्यापन', 'nav.monitoring': 'निगरानी',
    'nav.admin': 'एडमिन', 'nav.schemaAnalysis': 'स्कीमा विश्लेषण', 'nav.compatibilityCheck': 'संगतता जांच',
    'nav.assessmentReports': 'मूल्यांकन रिपोर्ट', 'nav.dataProfiling': 'डेटा प्रोफाइलिंग',
    'nav.running': 'चल रहा है', 'nav.queued': 'कतार में', 'nav.history': 'इतिहास',
    'nav.quickConvert': 'त्वरित रूपांतरण', 'nav.batch': 'बैच',
    'nav.queryHistory': 'क्वेरी इतिहास', 'nav.copyHistory': 'कॉपी इतिहास',
    'nav.taskHistory': 'कार्य इतिहास', 'nav.dynamicTables': 'डायनामिक टेबल', 'nav.governance': 'गवर्नेंस',
    'sidebar.darkMode': 'डार्क मोड', 'sidebar.lightMode': 'लाइट मोड', 'sidebar.language': 'भाषा',
    'sidebar.myProfile': 'मेरी प्रोफ़ाइल', 'sidebar.support': 'सहायता', 'sidebar.documentation': 'दस्तावेज़',
    'sidebar.privacyNotice': 'गोपनीयता', 'sidebar.signOut': 'साइन आउट',
    'assessments.title': 'मूल्यांकन', 'assessments.new': '+ नया', 'assessments.search': 'खोजें',
    'assessments.name': 'नाम', 'assessments.status': 'स्थिति', 'assessments.datasets': 'डेटासेट',
    'assessments.tables': 'टेबल', 'assessments.totalSize': 'कुल आकार',
    'assessments.startedAt': 'शुरू हुआ', 'assessments.completedAt': 'पूरा हुआ',
    'assessments.run': 'मूल्यांकन चलाएं', 'assessments.viewLogs': 'लॉग देखें',
    'assessments.viewReport': 'रिपोर्ट देखें', 'assessments.downloadReport': 'डाउनलोड करें',
    'assessments.edit': 'संपादित करें', 'assessments.delete': 'हटाएं',
    'assessments.deleteConfirm': 'मूल्यांकन हटाएं', 'assessments.deleteConfirmMsg': 'क्या आप इस मूल्यांकन को हटाना चाहते हैं? यह क्रिया पूर्ववत नहीं की जा सकती।',
    'assessments.cancel': 'रद्द करें', 'assessments.noAssessments': 'कोई मूल्यांकन नहीं',
    'assessments.noAssessmentsDesc': 'अपना पहला BigQuery मूल्यांकन बनाएं',
    'assessments.createFirst': 'पहला मूल्यांकन बनाएं', 'assessments.loading': 'लोड हो रहा है...',
    'assessments.started': 'मूल्यांकन शुरू हुआ', 'assessments.completed': 'पूर्ण',
    'assessments.failed': 'विफल', 'assessments.pending': 'लंबित',
    'assessments.rowsPerPage': 'प्रति पृष्ठ पंक्तियाँ:', 'assessments.showing': 'दिखा रहा है',
    'common.of': 'में से', 'common.retry': 'पुनः प्रयास',
  },
};

interface LanguageContextType {
  language: LanguageCode;
  setLanguage: (lang: LanguageCode) => void;
  t: (key: keyof TranslationKeys) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  t: (key) => key,
});

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<LanguageCode>(() => {
    const saved = localStorage.getItem('datamiq-language');
    return (saved as LanguageCode) || 'en';
  });

  const setLanguage = (lang: LanguageCode) => {
    setLanguageState(lang);
    localStorage.setItem('datamiq-language', lang);
  };

  const t = (key: keyof TranslationKeys): string => {
    return translations[language]?.[key] || translations.en[key] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
