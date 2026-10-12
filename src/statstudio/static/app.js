"use strict";

(() => {
  const state = { datasets: [], methods: [], history: [], dataset: null, method: null, result: null, busy: false };
  const $ = (id) => document.getElementById(id);
  const roleNames = {
    variables: "分析變數", columns: "分析欄位", variable: "分析變數", numeric_columns: "數值欄位",
    dependent: "依變數（結果）", dependent_variable: "依變數（結果）", outcome: "結果變數", target: "目標變數",
    predictors: "預測變數", independent: "自變數", independent_variables: "自變數", features: "分析特徵",
    group: "分組變數", group_column: "分組變數", group_by: "分組變數", factor: "分組因子",
    row: "列變數", rows: "列變數", row_variable: "列變數", column: "欄變數", column_variable: "欄變數",
    x: "X 變數", y: "Y 變數", first: "第一個變數", second: "第二個變數", before: "前測變數", after: "後測變數",
    weight: "加權欄位", weights: "加權欄位", pairs: "配對變數", event: "事件變數", time: "時間變數"
  };
  const parameterNames = {
    alpha: "顯著水準 α", confidence: "信賴水準", confidence_level: "信賴水準", alternative: "對立假設",
    missing: "遺漏值處理", nan_policy: "遺漏值處理", test_value: "檢定值", mu: "檢定值", popmean: "檢定平均數",
    equal_var: "等變異數假設", variance: "變異數方法", rotation: "轉軸方式", n_components: "成分數",
    n_factors: "因素數", n_clusters: "群集數", seed: "隨機種子", random_state: "隨機種子", max_iter: "迭代上限",
    method: "計算方式", correction: "連續性校正", bins: "直方圖組數", linkage: "連結方式", standardize: "標準化",
    intercept: "包含截距", ddof: "自由度校正", init: "初始中心方式", n_init: "重複初始次數"
  };

  function element(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = String(value);
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value === true ? "" : String(value));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function svgElement(tag, attrs = {}, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function stringify(value) {
    if (value === null || value === undefined) return "";
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }

  function format(value) {
    if (value === null || value === undefined || (typeof value === "number" && !Number.isFinite(value))) return "—";
    if (typeof value === "boolean") return value ? "是" : "否";
    if (typeof value !== "number") return stringify(value);
    if (Number.isInteger(value)) return value.toLocaleString("zh-TW", { maximumFractionDigits: 0 });
    if (Math.abs(value) < 0.00001 && value !== 0) return value.toExponential(5);
    return value.toLocaleString("zh-TW", { maximumSignificantDigits: 7 });
  }

  function notify(message, isError = false) {
    const node = $("notification");
    node.className = isError ? "notification error" : "notification";
    node.setAttribute("role", isError ? "alert" : "status");
    node.replaceChildren(element("button", { type: "button", "aria-label": "關閉訊息", onclick: () => { node.hidden = true; } }, "×"), document.createTextNode(message));
    node.hidden = false;
  }

  async function request(path, options) {
    const response = await fetch(path, options);
    let body;
    try { body = await response.json(); } catch { throw new Error("伺服器未回傳可讀取的資料。請檢查服務是否仍在執行。"); }
    if (!response.ok) {
      const message = typeof body.detail === "string" ? body.detail : stringify(body.detail || body.error || `HTTP ${response.status}`);
      throw new Error(message);
    }
    return body;
  }

  function fail(error) { notify(error instanceof Error ? error.message : String(error), true); }

  function setBusy(busy, message = "分析中…") {
    state.busy = busy;
    $("run-button").disabled = busy;
    $("demo-button").disabled = busy;
    $("welcome-demo").disabled = busy;
    $("upload-input").disabled = busy;
    $("analysis-form").setAttribute("aria-busy", String(busy));
    $("run-button").replaceChildren(busy ? element("span", { class: "spinner", "aria-hidden": "true" }) : element("span", { "aria-hidden": "true" }, "↗"), document.createTextNode(busy ? message : "執行分析"));
  }

  function switchTab(name, focus = false) {
    for (const button of document.querySelectorAll("[data-tab]")) {
      const selected = button.dataset.tab === name;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
      $(`panel-${button.dataset.tab}`).hidden = !selected;
      if (selected && focus) button.focus();
    }
  }

  function datasetId(dataset) { return String(dataset.id); }
  function columnName(column) { return typeof column === "string" ? column : String(column.name); }
  function columnType(column) { return typeof column === "string" ? "" : String(column.type || column.dtype || ""); }
  function isNumeric(column) { return /number|numeric|float|int|decimal|double/i.test(columnType(column)); }

  function renderDatasets() {
    $("dataset-count").textContent = String(state.datasets.length);
    const nodes = state.datasets.map((dataset) => {
      const selected = state.dataset && datasetId(dataset) === datasetId(state.dataset);
      const button = element("button", {
        class: `dataset-item${selected ? " selected" : ""}`, type: "button", "aria-pressed": String(Boolean(selected)),
        onclick: () => selectDataset(dataset.id).catch(fail)
      }, element("span", { class: "dataset-icon", "aria-hidden": "true" }, "▦"), element("span", { class: "dataset-item-text" },
        element("strong", { title: dataset.name || dataset.id }, dataset.name || dataset.id),
        element("small", {}, `${format(dataset.rows ?? 0)} 筆 · ${(dataset.columns || []).length} 欄位`)));
      return button;
    });
    $("dataset-list").replaceChildren(...(nodes.length ? nodes : [element("p", { class: "muted small" }, "尚未載入資料。") ]));
  }

  function renderDataset() {
    const dataset = state.dataset;
    $("welcome").hidden = Boolean(dataset);
    $("dataset-section").hidden = !dataset;
    $("analysis-grid").hidden = !dataset;
    if (!dataset) return;
    $("dataset-title").textContent = dataset.name || dataset.id;
    const columns = dataset.columns || [];
    const missing = columns.reduce((sum, column) => sum + (Number(column.missing) || 0), 0);
    $("dataset-metrics").replaceChildren(...[[format(dataset.rows || 0), "資料筆數"], [String(columns.length), "欄位"], [format(missing), "遺漏值"]].map(([value, label]) => element("div", { class: "metric" }, element("strong", {}, value), element("span", {}, label))));
    $("column-summary").replaceChildren(...columns.map((column) => element("div", { class: "column-chip" }, element("span", { class: "type-icon", "aria-hidden": "true" }, isNumeric(column) ? "#" : "A"), element("strong", {}, columnName(column)), element("small", {}, columnType(column) || "欄位"), Number(column.missing) > 0 ? element("small", { class: "missing-chip" }, `缺 ${column.missing}`) : null)));
    const preview = (dataset.preview || []).slice(0, 12);
    const names = columns.map(columnName);
    const rows = preview.map((row) => Array.isArray(row) ? row : names.map((name) => row[name]));
    $("dataset-preview").replaceChildren(renderTable(names, rows));
    renderMethodForm();
  }

  async function selectDataset(id) {
    if (state.busy) return;
    const dataset = await request(`/api/datasets/${encodeURIComponent(id)}`);
    state.dataset = dataset;
    state.result = null;
    $("result-content").hidden = true;
    $("result-placeholder").hidden = false;
    renderDatasets();
    renderDataset();
    switchTab("analysis");
  }

  function acceptDataset(dataset) {
    state.dataset = dataset;
    const index = state.datasets.findIndex((item) => datasetId(item) === datasetId(dataset));
    if (index >= 0) state.datasets[index] = dataset;
    else state.datasets.unshift(dataset);
    state.result = null;
    $("result-content").hidden = true;
    $("result-placeholder").hidden = false;
    renderDatasets();
    renderDataset();
    switchTab("analysis");
    notify(`已載入「${dataset.name || dataset.id}」，共 ${format(dataset.rows || 0)} 筆資料。`);
  }

  async function upload(file) {
    if (!file || state.busy) return;
    if (!/\.(csv|tsv|xlsx|sav|zsav)$/i.test(file.name)) { notify("請選擇 CSV、TSV、XLSX、SAV 或 ZSAV 格式的資料檔。", true); return; }
    setBusy(true, "匯入中…");
    try {
      const form = new FormData();
      form.append("file", file);
      acceptDataset(await request("/api/datasets/upload", { method: "POST", body: form }));
    } catch (error) { fail(error); }
    finally { setBusy(false); $("upload-input").value = ""; }
  }

  async function loadDemo() {
    if (state.busy) return;
    setBusy(true, "載入中…");
    try { acceptDataset(await request("/api/demo", { method: "POST" })); }
    catch (error) { fail(error); }
    finally { setBusy(false); }
  }

  function renderMethods() {
    $("method-select").replaceChildren(...state.methods.map((method) => element("option", { value: method.id }, method.label || method.id)));
    if (!state.methods.length) $("method-select").append(element("option", { value: "" }, "目前沒有可用方法"));
    state.method = state.methods[0] || null;
    renderMethodForm();
  }

  function renderMethodForm() {
    const method = state.methods.find((item) => item.id === $("method-select").value) || null;
    state.method = method;
    $("role-fields").replaceChildren();
    $("parameter-fields").replaceChildren();
    $("method-description").textContent = method ? method.description || "" : "";
    if (!method || !state.dataset) return;
    const columns = state.dataset.columns || [];
    for (const [role, spec] of Object.entries(method.roles || {})) {
      const type = typeof spec === "string" ? spec : spec.type || "single";
      const label = (typeof spec === "object" && spec.label) || roleNames[role] || role;
      const optional = type.startsWith("optional-");
      const multiple = type.endsWith("multi");
      if (multiple) {
        const fieldset = element("fieldset", { class: "role-fieldset", "data-role": role, "data-role-type": type });
        fieldset.append(element("legend", { class: "field-label" }, label + (optional ? "（選填）" : "")));
        const selection = element("div", { class: "selection-list" });
        columns.forEach((column, index) => {
          const name = columnName(column);
          const input = element("input", { type: "checkbox", name: role, value: name, id: `role-${role}-${index}` });
          selection.append(element("label", { class: "checkbox-label", for: input.id }, input, element("span", {}, name), element("small", {}, isNumeric(column) ? "數值" : "文字")));
        });
        fieldset.append(selection, element("span", { class: "role-hint" }, "可複選；分析前請確認各欄位的意義。"));
        $("role-fields").append(fieldset);
      } else {
        const select = element("select", { name: role, "data-role": role, "data-role-type": type, required: !optional });
        select.append(element("option", { value: "" }, optional ? "不指定" : "請選擇欄位"));
        columns.forEach((column) => select.append(element("option", { value: columnName(column) }, columnName(column))));
        $("role-fields").append(element("label", { class: "field" }, element("span", {}, label + (optional ? "（選填）" : "")), select));
      }
    }
    const parameters = method.parameters || [];
    if (parameters.length) $("parameter-fields").append(element("h3", { class: "parameter-heading" }, "分析選項"));
    for (const parameter of parameters) {
      let control;
      if (parameter.type === "select") {
        control = element("select", { name: parameter.key, "data-parameter": parameter.key });
        for (const choice of parameter.choices || []) {
          const value = choice && typeof choice === "object" ? choice.value : choice;
          const label = choice && typeof choice === "object" ? choice.label : choice;
          control.append(element("option", { value: JSON.stringify(value) }, typeof label === "boolean" ? (label ? "是" : "否") : label));
        }
        if (parameter.default !== undefined) control.value = JSON.stringify(parameter.default);
      } else {
        control = element("input", { type: "number", step: parameter.step || "any", name: parameter.key, "data-parameter": parameter.key, min: parameter.min, max: parameter.max });
        if (parameter.default !== undefined && parameter.default !== null) control.value = parameter.default;
      }
      $("parameter-fields").append(element("label", { class: "field" }, element("span", {}, parameter.label || parameterNames[parameter.key] || parameter.key), control));
    }
  }

  function collectOptions() {
    const options = {};
    for (const control of $("role-fields").querySelectorAll("[data-role]")) {
      const optional = control.dataset.roleType.startsWith("optional-");
      if (control.tagName === "FIELDSET") {
        const values = [...control.querySelectorAll("input:checked")].map((input) => input.value);
        if (!values.length && !optional) throw new Error(`請選擇「${roleNames[control.dataset.role] || control.dataset.role}」。`);
        if (values.length) options[control.dataset.role] = values;
      } else if (control.value !== "") options[control.dataset.role] = control.value;
    }
    for (const control of $("parameter-fields").querySelectorAll("[data-parameter]")) {
      if (control.value === "") continue;
      options[control.dataset.parameter] = control.tagName === "SELECT" ? JSON.parse(control.value) : Number(control.value);
    }
    return options;
  }

  async function analyze(event) {
    event.preventDefault();
    if (state.busy || !state.dataset || !state.method) return;
    let options;
    try { options = collectOptions(); } catch (error) { fail(error); return; }
    setBusy(true);
    $("notification").hidden = true;
    try {
      const result = await request("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: state.dataset.id, method: state.method.id, options }) });
      state.result = result;
      renderResult(result);
      await loadHistory();
    } catch (error) { fail(error); }
    finally { setBusy(false); }
  }

  function renderTable(columns, rows, maxRows = 200) {
    const table = element("table");
    const numeric = columns.map((_, index) => rows.some((row) => typeof row[index] === "number") && rows.every((row) => row[index] === null || row[index] === undefined || typeof row[index] === "number"));
    table.append(element("thead", {}, element("tr", {}, columns.map((column, index) => element("th", { scope: "col", class: numeric[index] ? "numeric" : "" }, typeof column === "object" ? column.label || column.name : column)))));
    const body = element("tbody");
    rows.slice(0, maxRows).forEach((row) => body.append(element("tr", {}, columns.map((_, index) => {
      const value = row[index];
      return element("td", { class: `${numeric[index] ? "numeric" : ""}${value === null || value === undefined ? " table-null" : ""}`, title: stringify(value) }, format(value));
    }))));
    if (!rows.length) body.append(element("tr", {}, element("td", { colspan: columns.length || 1, class: "muted" }, "沒有可顯示的資料。")));
    table.append(body);
    return table;
  }

  function compatibilityBox(compatibility = {}) {
    const status = String(compatibility.status || "unverified");
    const verified = /^(verified|validated|passed|oracle_verified|verified_for_fixture)$/.test(status);
    const labels = { verified: "指定案例已驗證", validated: "指定案例已驗證", passed: "指定案例已通過", oracle_verified: "指定 SPSS 案例已驗證", verified_for_fixture: "指定樣本已驗證", unverified: "SPSS 相容性待驗證", unverified_for_this_dataset: "此資料集的 SPSS 相容性尚未驗證", pending: "SPSS 相容性待驗證", partial: "部分案例已驗證", experimental: "實驗性方法", independent: "獨立實作 · 相容性待驗證", not_verified: "SPSS 相容性待驗證" };
    return element("div", { class: `compatibility-banner${verified ? " verified" : ""}` }, element("span", { class: "status-dot", "aria-hidden": "true" }), element("div", {}, element("strong", {}, labels[status] || `相容性狀態：${status}`), element("p", {}, compatibility.description || "尚未完成與 SPSS 的逐項結果比對。請檢視方法、預設值與分析警告。")));
  }

  function renderResult(result) {
    const container = $("result-content");
    container.replaceChildren();
    $("result-placeholder").hidden = true;
    container.hidden = false;
    const datasetName = result.dataset && (result.dataset.name || result.dataset.id);
    container.append(element("div", { class: "result-heading" }, element("div", {}, element("span", { class: "step-label" }, "03 / 結果"), element("h2", {}, result.title || result.method || "分析結果"), element("p", { class: "result-subtitle" }, [datasetName, dateText(result.created_at), `ID ${result.id}`].filter(Boolean).join(" · ")))));
    if (result.id !== undefined) container.append(element("div", { class: "result-actions" }, element("a", { class: "button button-subtle", href: `/api/results/${encodeURIComponent(result.id)}/report`, download: "" }, "↓ HTML 報告"), element("a", { class: "button button-subtle", href: `/api/results/${encodeURIComponent(result.id)}/json`, download: "" }, "↓ 完整 JSON")));
    container.append(compatibilityBox(result.compatibility));
    if (result.warnings && result.warnings.length) container.append(element("div", { class: "warning-box", role: "note" }, element("strong", {}, "分析提醒"), element("ul", {}, result.warnings.map((warning) => element("li", {}, warning)))));
    const tables = result.tables || [];
    for (const table of tables) {
      const columns = table.columns || [];
      const rows = (table.rows || []).map((row) => Array.isArray(row) ? row : columns.map((column) => row[typeof column === "object" ? column.name : column]));
      const card = element("section", { class: "card result-card" }, element("div", { class: "card-heading" }, element("h3", {}, table.title || "結果表"), element("small", {}, `${rows.length} 列`)), element("div", { class: "table-scroll", tabindex: "0", "aria-label": table.title || "結果表" }, renderTable(columns, rows)));
      if (rows.length > 200) card.append(element("p", { class: "table-footer" }, "畫面顯示前 200 列。完整結果請下載 JSON 或 HTML 報告。"));
      container.append(card);
    }
    for (const chart of result.charts || []) container.append(renderChart(chart));
    if (!tables.length && !(result.charts || []).length) container.append(element("div", { class: "card result-card" }, element("p", { class: "table-footer" }, "此分析未回傳結果表或圖表，請查看下方的計算詳情。")));
    const details = { method: result.method, details: result.details || {}, provenance: result.provenance || {}, compatibility: result.compatibility || {} };
    container.append(element("details", { class: "result-details" }, element("summary", {}, "查看分析選項、引擎資訊與驗證紀錄"), element("pre", {}, JSON.stringify(details, null, 2))));
    container.append(element("p", { class: "workspace-footnote" }, "畫面數字最多顯示 7 位有效數字；游標停留在數值上可查看原值。完整精度保留於 JSON。"));
  }

  function chartBase(title, xLabel = "", yLabel = "") {
    const svg = svgElement("svg", { viewBox: "0 0 620 320", role: "img", "aria-label": title || "統計圖表" });
    svg.append(svgElement("title", {}, title || "統計圖表"));
    const area = { left: 60, right: 601, top: 22, bottom: 258 };
    area.width = area.right - area.left;
    area.height = area.bottom - area.top;
    if (xLabel) svg.append(svgElement("text", { x: (area.left + area.right) / 2, y: 312, "text-anchor": "middle", fill: "#85977f", "font-size": 10 }, xLabel));
    if (yLabel) svg.append(svgElement("text", { transform: "translate(15 142) rotate(-90)", "text-anchor": "middle", fill: "#85977f", "font-size": 10 }, yLabel));
    return { svg, area };
  }

  function axisY(svg, area, min, max) {
    for (let index = 0; index <= 4; index++) {
      const value = min + (max - min) * index / 4;
      const y = area.bottom - area.height * index / 4;
      svg.append(svgElement("line", { x1: area.left, x2: area.right, y1: y, y2: y, stroke: "#eaf0e4", "stroke-width": 1 }));
      svg.append(svgElement("text", { x: area.left - 9, y: y + 3.5, "text-anchor": "end", fill: "#92a088", "font-size": 9 }, tickText(value)));
    }
    svg.append(svgElement("line", { x1: area.left, x2: area.right, y1: area.bottom, y2: area.bottom, stroke: "#cfdcca" }));
  }

  function tickText(value) {
    if (value !== 0 && (Math.abs(value) >= 1e6 || Math.abs(value) < 0.001)) return value.toExponential(1);
    return Number(value.toPrecision(4)).toLocaleString("zh-TW", { maximumFractionDigits: 5 });
  }

  function extent(values) {
    let min = Infinity, max = -Infinity;
    for (const value of values) { if (value < min) min = value; if (value > max) max = value; }
    if (min === max) { const pad = Math.abs(min) * 0.05 || 0.5; return [min - pad, max + pad]; }
    return [min, max];
  }

  function numericValues(values) { return (values || []).filter((value) => typeof value === "number" && Number.isFinite(value)); }

  function drawHistogram(chart) {
    const values = numericValues(chart.values);
    if (!values.length) return { empty: true };
    const [min, max] = extent(values);
    const bins = Math.min(60, Math.max(1, Math.round(Number(chart.bins) || Math.ceil(Math.log2(values.length) + 1))));
    const width = (max - min) / bins;
    const counts = new Array(bins).fill(0);
    for (const value of values) counts[Math.min(bins - 1, Math.max(0, Math.floor((value - min) / width)))]++;
    const yMax = Math.max(...counts) || 1;
    const { svg, area } = chartBase(chart.title, chart.x_label || "數值", "次數");
    axisY(svg, area, 0, yMax);
    counts.forEach((count, index) => {
      const barWidth = area.width / bins;
      const height = count / yMax * area.height;
      const bar = svgElement("rect", { x: area.left + index * barWidth + 1, y: area.bottom - height, width: Math.max(1, barWidth - 2), height, fill: "#7ba58b", rx: 2 });
      bar.append(svgElement("title", {}, `${format(min + index * width)}–${format(min + (index + 1) * width)}：${count}`));
      svg.append(bar);
    });
    for (let index = 0; index <= 4; index++) svg.append(svgElement("text", { x: area.left + area.width * index / 4, y: area.bottom + 18, "text-anchor": "middle", fill: "#92a088", "font-size": 9 }, tickText(min + (max - min) * index / 4)));
    return { svg, caption: `${values.length.toLocaleString("zh-TW")} 個有效值 · ${bins} 組。分組僅用於圖形顯示。` };
  }

  function drawScatter(chart) {
    const points = [];
    const xValues = chart.x || [], yValues = chart.y || [];
    for (let index = 0; index < Math.min(xValues.length, yValues.length); index++) if (typeof xValues[index] === "number" && typeof yValues[index] === "number" && Number.isFinite(xValues[index]) && Number.isFinite(yValues[index])) points.push([xValues[index], yValues[index]]);
    if (!points.length) return { empty: true };
    const [xMin, xMax] = extent(points.map((point) => point[0]));
    const [yMin, yMax] = extent(points.map((point) => point[1]));
    const { svg, area } = chartBase(chart.title, chart.x_label || "X", chart.y_label || "Y");
    axisY(svg, area, yMin, yMax);
    for (let index = 0; index <= 4; index++) svg.append(svgElement("text", { x: area.left + area.width * index / 4, y: area.bottom + 18, "text-anchor": "middle", fill: "#92a088", "font-size": 9 }, tickText(xMin + (xMax - xMin) * index / 4)));
    const stride = Math.max(1, Math.ceil(points.length / 1500));
    let displayed = 0;
    for (let index = 0; index < points.length; index += stride) {
      const point = points[index];
      const circle = svgElement("circle", { cx: area.left + (point[0] - xMin) / (xMax - xMin) * area.width, cy: area.bottom - (point[1] - yMin) / (yMax - yMin) * area.height, r: 3.2, fill: "#6f9e84", "fill-opacity": .7, stroke: "#fff", "stroke-width": .7 });
      circle.append(svgElement("title", {}, `(${format(point[0])}, ${format(point[1])})`));
      svg.append(circle); displayed++;
    }
    return { svg, caption: stride > 1 ? `資料共 ${points.length.toLocaleString("zh-TW")} 點；圖形等間隔取樣顯示 ${displayed.toLocaleString("zh-TW")} 點，計算結果不受影響。` : `${points.length.toLocaleString("zh-TW")} 個有效配對值。` };
  }

  function drawBar(chart) {
    const labels = chart.labels || [];
    const values = chart.values || [];
    const pairs = labels.map((label, index) => [stringify(label), values[index]]).filter((pair) => typeof pair[1] === "number" && Number.isFinite(pair[1]));
    if (!pairs.length) return { empty: true };
    const shown = pairs.slice(0, 40);
    const min = Math.min(0, ...shown.map((pair) => pair[1]));
    const max = Math.max(0, ...shown.map((pair) => pair[1]));
    const range = max - min || 1;
    const { svg, area } = chartBase(chart.title, chart.x_label || "", chart.y_label || "數值");
    axisY(svg, area, min, min + range);
    const zeroY = area.bottom - (0 - min) / range * area.height;
    const barWidth = area.width / shown.length;
    const labelStride = Math.max(1, Math.ceil(shown.length / 9));
    shown.forEach(([label, value], index) => {
      const valueY = area.bottom - (value - min) / range * area.height;
      const bar = svgElement("rect", { x: area.left + index * barWidth + barWidth * .2, y: Math.min(valueY, zeroY), width: Math.max(1, barWidth * .6), height: Math.abs(zeroY - valueY), fill: "#7ca38d", rx: 2 });
      bar.append(svgElement("title", {}, `${label}：${format(value)}`));
      svg.append(bar);
      if (index % labelStride === 0) {
        const text = svgElement("text", { x: area.left + (index + .5) * barWidth, y: area.bottom + 19, "text-anchor": "middle", fill: "#92a088", "font-size": 9 }, label.length > 9 ? `${label.slice(0, 8)}…` : label);
        text.append(svgElement("title", {}, label));
        svg.append(text);
      }
    });
    return { svg, caption: pairs.length > 40 ? `共 ${pairs.length} 個類別；畫面顯示前 40 個，其餘請查看結果表。` : `${pairs.length} 個類別。將游標停在長條上可查看完整標籤與數值。` };
  }

  function renderChart(chart) {
    const card = element("section", { class: "card result-card" }, element("div", { class: "card-heading" }, element("h3", {}, chart.title || "圖表")));
    const container = element("div", { class: "chart-container" });
    const draw = { histogram: drawHistogram, scatter: drawScatter, bar: drawBar }[chart.kind];
    if (!draw) container.append(element("p", { class: "chart-caption" }, `此介面尚未支援 ${chart.kind || "未知"} 圖形。原始圖表資料保留在 JSON。`));
    else {
      const result = draw(chart);
      if (result.empty) container.append(element("p", { class: "chart-caption" }, "沒有可繪圖的有效數值。"));
      else container.append(result.svg, element("p", { class: "chart-caption" }, result.caption));
    }
    card.append(container);
    return card;
  }

  function dateText(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat("zh-TW", { dateStyle: "short", timeStyle: "short" }).format(date);
  }

  async function loadHistory() {
    const response = await request("/api/results");
    state.history = response.results || [];
    renderHistory();
  }

  function renderHistory() {
    $("history-count").textContent = String(state.history.length);
    if (!state.history.length) {
      $("history-list").replaceChildren(element("div", { class: "history-empty" }, element("h3", {}, "尚未建立分析紀錄"), element("p", { class: "small" }, "執行第一個分析後，即可在這裡重新開啟結果。")));
      return;
    }
    $("history-list").replaceChildren(...state.history.map((result, index) => element("article", { class: "history-item" }, element("span", { class: "history-number", "aria-hidden": "true" }, String(index + 1).padStart(2, "0")), element("div", { class: "history-text" }, element("h3", {}, result.title || result.method), element("p", {}, [result.method, dateText(result.created_at)].filter(Boolean).join(" · "))), element("button", { class: "button button-secondary", type: "button", onclick: () => openResult(result.id).catch(fail) }, "開啟 ↗"))));
  }

  async function openResult(id) {
    if (state.busy) return;
    const result = await request(`/api/results/${encodeURIComponent(id)}`);
    if (result.dataset && result.dataset.id !== undefined) {
      try { state.dataset = await request(`/api/datasets/${encodeURIComponent(result.dataset.id)}`); renderDatasets(); renderDataset(); }
      catch { /* 已保存的結果可在來源資料不再可用時獨立閱讀。 */ }
    }
    state.result = result;
    $("welcome").hidden = true;
    $("analysis-grid").hidden = false;
    renderResult(result);
    switchTab("analysis");
    $("results-region").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function copyText(text, button) {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      const original = button.textContent;
      button.textContent = "已複製";
      setTimeout(() => { button.textContent = original; }, 1800);
    } catch {
      notify("瀏覽器未允許自動複製，請選取畫面上的文字後按 Ctrl+C。", true);
    }
  }

  function renderAIExamples() {
    const examples = [
      ["先認識資料", "請使用 StatStudio 的 MCP 工具，列出我的資料集。先檢查各欄位型態、遺漏值與資料筆數，再說明適合做哪些描述統計。"],
      ["比較兩組差異", "請使用 StatStudio，先檢視資料中的分組欄位與數值欄位，和我確認要比較的變數，再做適合的兩組比較。列出方法假設、信賴區間及分析警告。"],
      ["建立可解讀的模型", "我想用 StatStudio 建立迴歸模型。請先和我確認依變數與預測變數，檢查遺漏值，再執行分析。解釋係數與模型限制，並保留完整結果。"],
      ["檢查與整理结果", "請使用 StatStudio 檢視最近的分析結果，列出實際分析選項、計算引擎版本與 SPSS 相容性狀態。請清楚區分已驗證的項目和仍待驗證的項目。"]
    ];
    $("ai-examples").replaceChildren(...examples.map(([title, prompt]) => {
      const button = element("button", { class: "copy-button", type: "button" }, "複製範例");
      button.addEventListener("click", () => copyText(prompt, button));
      return element("article", { class: "ai-example" }, element("h3", {}, title), element("p", {}, prompt), button);
    }));
  }

  function bindEvents() {
    document.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => switchTab(button.dataset.tab));
      button.addEventListener("keydown", (event) => {
        const buttons = [...document.querySelectorAll("[data-tab]")];
        const index = buttons.indexOf(button);
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % buttons.length;
        if (event.key === "ArrowLeft") next = (index + buttons.length - 1) % buttons.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = buttons.length - 1;
        if (next !== undefined) { event.preventDefault(); switchTab(buttons[next].dataset.tab, true); }
      });
    });
    $("upload-input").addEventListener("change", (event) => upload(event.target.files[0]));
    $("demo-button").addEventListener("click", loadDemo);
    $("welcome-demo").addEventListener("click", loadDemo);
    $("method-select").addEventListener("change", renderMethodForm);
    $("analysis-form").addEventListener("submit", analyze);
    $("refresh-history").addEventListener("click", () => loadHistory().catch(fail));
    $("copy-mcp").addEventListener("click", () => copyText($("mcp-command").textContent, $("copy-mcp")));
    const zone = $("drop-zone");
    zone.addEventListener("dragover", (event) => { event.preventDefault(); if (!state.busy) zone.classList.add("dragging"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("dragging");
      if (event.dataTransfer.files.length > 1) notify("一次僅匯入一份資料；本次會載入第一個檔案。");
      upload(event.dataTransfer.files[0]);
    });
    window.addEventListener("dragover", (event) => { if ([...(event.dataTransfer?.types || [])].includes("Files")) event.preventDefault(); });
    window.addEventListener("drop", (event) => { if (event.dataTransfer?.files?.length) event.preventDefault(); });
  }

  async function initialize() {
    bindEvents();
    renderAIExamples();
    renderHistory();
    const responses = await Promise.allSettled([request("/api/methods"), request("/api/datasets"), loadHistory()]);
    if (responses[0].status === "fulfilled") { state.methods = responses[0].value.methods || []; renderMethods(); }
    if (responses[1].status === "fulfilled") {
      state.datasets = responses[1].value.datasets || [];
      renderDatasets();
      if (state.datasets.length) { state.dataset = state.datasets[0]; renderDataset(); renderDatasets(); }
    }
    const failures = responses.filter((result) => result.status === "rejected");
    if (failures.length) {
      $("connection-status").textContent = "連線需要檢查";
      fail(failures[0].reason);
    } else $("connection-status").textContent = "服務已連線";
  }

  initialize().catch(fail);
})();
