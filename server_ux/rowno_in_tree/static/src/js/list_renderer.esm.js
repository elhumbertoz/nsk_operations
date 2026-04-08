/* @odoo-module */

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

patch(ListRenderer.prototype, {
  get nbCols() {
    // Llamar al método original y agregar 1 por nuestra columna de números de fila
    const originalNbCols = super.nbCols;
    return originalNbCols + 1;
  },

  get originalNbCols() {
    // Getter auxiliar para obtener el nbCols original sin nuestra columna
    return super.nbCols;
  },

  freezeColumnWidths() {
    const table = this.tableRef.el;
    const child_table = table.firstElementChild.firstElementChild;
    if (!$(child_table.firstChild).hasClass("o_list_row_count_sheliya")) {
      const a = $(child_table).prepend(
        '<th class="o_list_row_number_header o_list_row_count_sheliya position-relative">' +
        '<div class="d-flex align-items-center">' +
        '<span>#</span>' +
        '<span class="o_resize position-absolute top-0 end-0 bottom-0 ps-1 bg-black-25 opacity-0 opacity-50-hover z-index-1" style="cursor: col-resize;"></span>' +
        '</div>' +
        '</th>'
      );

      // Agregar event listener para el redimensionamiento
      const resizeHandler = a.find("th.o_list_row_count_sheliya .o_resize")[0];
      if (resizeHandler) {
        resizeHandler.addEventListener('pointerdown', (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          this.onStartResizeRowNumber(ev);
        });
      }
    }

    // Llamar al método original primero
    const result = super.freezeColumnWidths();

    // Aplicar estilos después de que Odoo haya calculado los anchos
    const rowNumberHeader = table.querySelector('th.o_list_row_count_sheliya');
    if (rowNumberHeader) {
      // Calcular ancho dinámico basado en el número máximo de registros
      const maxRecords = this.props.list.count || this.props.list.records.length;
      const maxDigits = maxRecords.toString().length;

      // Calcular ancho necesario: 8px por dígito + 16px de padding
      const dynamicWidth = Math.max(33, (maxDigits * 8) + 16);

      if (this.isEmpty) {
        rowNumberHeader.style.width = `${dynamicWidth}px`;
      } else {
        rowNumberHeader.style.minWidth = `${dynamicWidth}px`;
        rowNumberHeader.style.maxWidth = `${dynamicWidth}px`;
      }
    }

    return result;
  },

  setDefaultColumnWidths() {
    const widths = this.state.columns.map((col) => this.calculateColumnWidth(col));
    const sumOfRelativeWidths = widths
      .filter(({ type }) => type === "relative")
      .reduce((sum, { value }) => sum + value, 0);

    // Ajustar columnOffset para considerar nuestra columna adicional
    // Odoo original: hasSelectors ? 2 : 1
    // Nosotros: +1 para nuestra columna de números de fila
    const columnOffset = (this.hasSelectors ? 2 : 1) + 1;

    // Aplicar ancho dinámico a nuestra columna de números de fila
    const rowNumberHeader = this.tableRef.el.querySelector('th.o_list_row_count_sheliya');
    if (rowNumberHeader) {
      const maxRecords = this.props.list.count || this.props.list.records.length;
      const maxDigits = maxRecords.toString().length;
      const dynamicWidth = Math.max(33, (maxDigits * 8) + 16);

      if (this.isEmpty) {
        rowNumberHeader.style.width = `${dynamicWidth}px`;
      } else {
        rowNumberHeader.style.minWidth = `${dynamicWidth}px`;
        rowNumberHeader.style.maxWidth = `${dynamicWidth}px`;
      }
    }

    widths.forEach(({ type, value }, i) => {
      const headerEl = this.tableRef.el.querySelector(`th:nth-child(${i + columnOffset})`);
      if (type === "absolute") {
        if (this.isEmpty) {
          headerEl.style.width = value;
        } else {
          headerEl.style.minWidth = value;
        }
      } else if (type === "relative" && this.isEmpty) {
        headerEl.style.width = `${((value / sumOfRelativeWidths) * 100).toFixed(2)}%`;
      }
    });
  },

  // Método para manejar el redimensionamiento de la columna de números de fila
  onStartResizeRowNumber(ev) {
    this.resizing = true;
    const table = this.tableRef.el;
    const th = ev.target.closest("th");
    const handler = th.querySelector(".o_resize");

    // Fijar el ancho de la tabla para evitar cambios de layout
    table.style.width = `${Math.floor(table.getBoundingClientRect().width)}px`;

    // Obtener todas las celdas de la columna de números de fila
    const resizingColumnElements = [...table.getElementsByTagName("tr")]
      .map(tr => tr.querySelector("td.o_list_row_count_sheliya, th.o_list_row_count_sheliya"))
      .filter(el => el !== null);

    const initialX = ev.clientX;
    const initialWidth = th.getBoundingClientRect().width;
    const initialTableWidth = table.getBoundingClientRect().width;
    const resizeStoppingEvents = ["keydown", "pointerdown", "pointerup"];

    // Fijar el ancho del contenedor padre si es necesario
    if (!this.rootRef.el.style.width) {
      this.rootWidthFixed = true;
      this.rootRef.el.style.width = `${Math.floor(
        this.rootRef.el.getBoundingClientRect().width
      )}px`;
    }

    // Cambiar el estilo del handler durante el redimensionamiento
    if (handler) {
      handler.classList.add("bg-primary", "opacity-100");
      handler.classList.remove("bg-black-25", "opacity-50-hover");
    }

    // Evento mousemove: redimensionar header
    const resizeHeader = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const delta = ev.clientX - initialX;
      const newWidth = Math.max(33, initialWidth + delta); // Ancho mínimo de 33px
      const tableDelta = newWidth - initialWidth;

      // Aplicar el nuevo ancho a todas las celdas de la columna
      resizingColumnElements.forEach(el => {
        el.style.width = `${Math.floor(newWidth)}px`;
        el.style.minWidth = `${Math.floor(newWidth)}px`;
        el.style.maxWidth = `${Math.floor(newWidth)}px`;
      });

      // Ajustar el ancho de la tabla
      table.style.width = `${Math.floor(initialTableWidth + tableDelta)}px`;
    };

    window.addEventListener("pointermove", resizeHeader);

    // Eventos para detener el redimensionamiento
    const stopResize = (ev) => {
      this.resizing = false;

      // Restaurar el estilo del handler
      if (handler) {
        handler.classList.remove("bg-primary", "opacity-100");
        handler.classList.add("bg-black-25", "opacity-50-hover");
      }

      // Restaurar el ancho del contenedor padre si se fijó
      if (this.rootWidthFixed) {
        this.rootRef.el.style.width = null;
        this.rootWidthFixed = false;
      }

      // Remover event listeners
      window.removeEventListener("pointermove", resizeHeader);
      for (const eventType of resizeStoppingEvents) {
        window.removeEventListener(eventType, stopResize);
      }
    };

    // Agregar event listeners para detener el redimensionamiento
    for (const eventType of resizeStoppingEvents) {
      window.addEventListener(eventType, stopResize);
    }
  },
});
