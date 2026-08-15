import { computed, ref, watch, type Ref } from "vue";

export function useClientPagination<T>(rows: Ref<T[]>, defaultPageSize = 10) {
  const page = ref(1);
  const pageSize = ref(defaultPageSize);
  const total = computed(() => rows.value.length);
  const pagedRows = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return rows.value.slice(start, start + pageSize.value);
  });

  function updatePageSize(value: number) {
    pageSize.value = value;
    page.value = 1;
  }

  watch(total, (nextTotal) => {
    const maxPage = Math.max(1, Math.ceil(nextTotal / pageSize.value));
    if (page.value > maxPage) page.value = maxPage;
  });

  return { page, pageSize, total, pagedRows, updatePageSize };
}
