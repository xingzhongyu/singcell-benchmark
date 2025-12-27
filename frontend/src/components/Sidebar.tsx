// src/components/Sidebar.tsx

import React from 'react';
import './Sidebar.css';

interface SidebarProps {
    activePage: 'preprocessing' | 'grn';
    onPageChange: (page: 'preprocessing' | 'grn') => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activePage, onPageChange }) => {
    return (
        <nav className="sidebar">
            <ul>
                <li 
                    className={activePage === 'preprocessing' ? 'active' : ''}
                    onClick={() => onPageChange('preprocessing')}
                >
                    预处理
                </li>
                <li 
                    className={activePage === 'grn' ? 'active' : ''}
                    onClick={() => onPageChange('grn')}
                >
                    GRN 推断
                </li>
            </ul>
        </nav>
    );
};

export default Sidebar;