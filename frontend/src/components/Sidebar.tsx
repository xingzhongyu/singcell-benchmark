// src/components/Sidebar.tsx

import React from 'react';
import './Sidebar.css'; // The CSS import remains the same

// Define the component as a React Functional Component (React.FC).
// The empty angle brackets <> (or <{}>) indicate it takes no custom props.
const Sidebar: React.FC = () => {
    return (
        <nav className="sidebar">
            <ul>
                {/* 默认选中 "预处理" */}
                <li className="active">预处理</li>
                {/* 未来可以添加更多导航项 */}
                {/* <li>分析结果</li> */}
            </ul>
        </nav>
    );
};

export default Sidebar;