"""SQLAlchemy model package."""

from app.models.business_extensions import (  # noqa: F401,E402
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseReturnItem,
    SalesQuote,
    SalesQuoteItem,
    SalesReturnItem,
)
from app.models.system import SysOrgMembership  # noqa: F401,E402
from app.models.platform import ExtEventDelivery, ExtEventOutbox, ExtEventSubscription, SysApiClient  # noqa: F401,E402
from app.models.collaboration import (  # noqa: F401,E402
    BizAttachment,
    BizComment,
    BizDocument,
    BizDocumentRelation,
    BizExportJob,
    BizReportDefinition,
    BizReportRun,
    BizSavedView,
    SysIdempotencyRecord,
    SysNotification,
)
from app.models.cost import CostAllocation, CostPeriodClose, CostProjectEntry  # noqa: F401,E402
from app.models.crm import CrmContact, CrmFollowUp, CrmLead, CrmOpportunity  # noqa: F401,E402
from app.models.quality import QaCapaAction, QaDefectCatalog, QaInspection, QaNonconformity, QaPlan  # noqa: F401,E402
from app.models.hr import HrAttendance, HrEmployee, HrPayroll  # noqa: F401,E402
from app.models.finance import (  # noqa: F401,E402
    FinAccount,
    FinAccountingDimension,
    FinAssetDepreciation,
    FinBankAccount,
    FinFiscalPeriod,
    FinCurrency,
    FinExchangeRate,
    FinBudget,
    FinCashForecast,
    FinReconciliationStatement,
)
from app.models.inventory_advanced import (  # noqa: F401,E402
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvReservation,
    InvTraceEvent,
    InvLocation,
    InvPickWave,
    InvSlowMovingRule,
    InvScanRecord,
    InvWarehouseTask,
    InvWarehouseAccess,
    InvZone,
)
from app.models.production import (  # noqa: F401,E402
    MfgBom,
    MfgBomItem,
    MfgCapacityCalendar,
    MfgAlternateMaterial,
    MfgMaterialIssue,
    MfgMaterialIssueItem,
    MfgMaterialReturn,
    MfgMaterialReturnItem,
    MfgMps,
    MfgMrpResult,
    MfgMrpRun,
    MfgReport,
    MfgRouting,
    MfgRoutingOperation,
    MfgSubcontractOrder,
    MfgSubcontractReceipt,
    MfgWorkOrder,
    MfgWorkOrderCost,
    MfgWorkOrderException,
    MfgWorkOrderMaterial,
    MfgWorkOrderSchedule,
    MfgWorkCenter,
)
