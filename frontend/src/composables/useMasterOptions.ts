import { ref } from "vue";

import { listMasterData, type MasterResource } from "../api/master-data";

export type SelectOption = { label: string; value: string };

function rowsFrom(response: any): any[] {
  const data = response?.data?.data;
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}

export function useMasterOptions() {
  const customers = ref<SelectOption[]>([]);
  const suppliers = ref<SelectOption[]>([]);
  const materials = ref<SelectOption[]>([]);
  const warehouses = ref<SelectOption[]>([]);

  async function loadResource(resource: MasterResource, target: { value: SelectOption[] }) {
    const response = await listMasterData(resource, { page: 1, pageSize: 200 });
    target.value = rowsFrom(response).map((row) => ({
      label: `${row.name || row.code || row.id}${row.code ? `（${row.code}）` : ""}`,
      value: String(row.id),
    }));
  }

  async function loadOptions(resources: MasterResource[] = ["customers", "suppliers", "materials", "warehouses"]) {
    await Promise.all(resources.map((resource) => {
      const target = resource === "customers" ? customers : resource === "suppliers" ? suppliers : resource === "materials" ? materials : warehouses;
      return loadResource(resource, target);
    }));
  }

  return { customers, suppliers, materials, warehouses, loadOptions };
}
