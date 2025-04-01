import React from 'react';
import { TaskStatus } from '../types'; // Ensure AnalysisProgressMeta, TaskFailureResult are defined here

interface TaskProgressProps {
    status: TaskStatus | null;
}

// Helper to safely get nested properties
const getFromResult = (result: any, key: string): any | undefined => {
    if (result && typeof result === 'object' && key in result) {
        return result[key];
    }
    return undefined;
}


const TaskProgress: React.FC<TaskProgressProps> = ({ status }) => {
    if (!status) return null;

    let progressPercent = 0;
    let message = `Status: ${status.status}`;
    let resultDetails: string | null = null;

    const result = status.result; // Can be TaskProgressMeta, TaskSuccessResult, TaskFailureResult, etc.

    if (status.status === 'PROGRESS' || status.status === 'STARTED') {
         const metaStatus = getFromResult(result, 'status');
         const step = getFromResult(result, 'step');
         const totalSteps = getFromResult(result, 'total_steps');

         message = metaStatus || `Status: ${status.status}`;
         if (step && totalSteps) {
            progressPercent = Math.max(0, Math.min(100, Math.round((step / totalSteps) * 100)));
            message += ` (Step ${step} of ${totalSteps})`;
         } else if (status.status === 'STARTED') {
             progressPercent = 5; // Small progress for 'STARTED'
         } else {
             progressPercent = 50; // Default progress if steps unknown
         }
    } else if (status.status === 'SUCCESS') {
         message = getFromResult(result, 'status') || 'Analysis Complete!'; // Use status from result if available
         progressPercent = 100;
         // Optionally display summary keys from results_summary?
         // const summary = getFromResult(result, 'results_summary');
         // if (summary) resultDetails = `Completed Steps: ${Object.keys(summary).join(', ')}`;

    } else if (status.status === 'FAILURE') {
         const error = getFromResult(result, 'error') || getFromResult(result, 'details') || 'Unknown error';
         const traceback = getFromResult(result, 'traceback');
         message = `Analysis Failed: ${error}`;
         progressPercent = 100; // Show bar as full/red
         if (traceback) {
             console.error("Task Failed Traceback:", traceback); // Log traceback for dev
             // Optionally make traceback visible in UI (e.g., in a collapsed section)
             resultDetails = "See browser console for detailed error traceback.";
         }
    } else if (status.status === 'PENDING') {
         message = "Task Queued...";
         progressPercent = 0;
    } else if (status.status === 'REVOKED') {
         message = "Task Revoked/Cancelled";
         progressPercent = 0;
    }


    return (
        <div className="task-progress" style={{ marginTop: '5px', marginBottom: '5px', padding: '5px', border: '1px solid #eee', borderRadius: '4px' }}>
            <p style={{ margin: '0 0 5px 0', fontSize: '0.9em' }}>{message}</p>
            <progress
                value={progressPercent}
                max="100"
                style={{ width: '100%', accentColor: status.status === 'FAILURE' ? 'red' : undefined }}
             />
             {resultDetails && <p style={{ fontSize: '0.8em', color: '#666', margin: '5px 0 0 0' }}>{resultDetails}</p>}
        </div>
    );
};

export default TaskProgress;