var dagcomponentfuncs = window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {};

// 타이핑 + 드롭다운이 모두 가능한 마법의 에디터 생성
dagcomponentfuncs.DatalistEditor = class {
    init(params) {
        // 1. 텍스트 입력창(Input) 생성
        this.eInput = document.createElement('input');
        this.eInput.value = params.value || '';
        this.eInput.setAttribute('list', 'list-' + params.column.colId);
        this.eInput.style.width = '100%';
        this.eInput.style.height = '100%';
        this.eInput.style.border = 'none';
        this.eInput.style.outline = 'none';
        this.eInput.style.padding = '0 10px';

        // 2. 드롭다운 목록(DataList) 생성
        this.datalist = document.createElement('datalist');
        this.datalist.id = 'list-' + params.column.colId;
        
        params.values.forEach(val => {
            let opt = document.createElement('option');
            opt.value = val;
            this.datalist.appendChild(opt);
        });

        // 3. 하나로 합치기
        this.container = document.createElement('div');
        this.container.style.width = '100%';
        this.container.style.height = '100%';
        this.container.appendChild(this.eInput);
        this.container.appendChild(this.datalist);
    }
    getGui() { return this.container; }
    afterGuiAttached() { this.eInput.focus(); this.eInput.select(); } // 열리자마자 텍스트 선택
    getValue() { return this.eInput.value; }
};