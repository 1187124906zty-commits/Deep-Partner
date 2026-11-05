import { Extension, Mark, Editor } from '@tiptap/core';
import { PluginKey } from '@tiptap/pm/state';

interface ChangeAuthor {
    id: string;
    name: string;
    color: string;
}
type TrackChangesMode = 'edit' | 'suggest' | 'view';
interface TrackChangesOptions {
    author: ChangeAuthor;
    mode?: TrackChangesMode;
    onStatusChange?: (changeId: string, status: 'accepted' | 'rejected') => void;
    additionalBlockTypes?: string[];
}
interface TrackChangesStorage {
    mode: TrackChangesMode;
    author: ChangeAuthor;
}
interface TrackedChangeInfo {
    changeId: string;
    type: 'insertion' | 'deletion' | 'formatChange' | 'nodeChange';
    authorId: string;
    authorName: string;
    authorColor: string;
    timestamp: string;
    from: number;
    to: number;
    text: string;
    formatAdded?: string;
    formatRemoved?: string;
}
interface ChangeMarkAttributes {
    changeId: string;
    authorId: string;
    authorName: string;
    authorColor: string;
    timestamp: string;
}
interface NodeChangeTracking {
    changeId: string;
    authorId: string;
    authorName: string;
    authorColor: string;
    timestamp: string;
    originalType: string;
    originalAttrs?: Record<string, unknown>;
}

declare const TrackChangesExtension: Extension<TrackChangesOptions, TrackChangesStorage>;

declare module '@tiptap/core' {
    interface Commands<ReturnType> {
        insertion: {
            setInsertion: (attributes: Record<string, string>) => ReturnType;
            unsetInsertion: () => ReturnType;
        };
    }
}
declare const InsertionMark: Mark<any, any>;

declare module '@tiptap/core' {
    interface Commands<ReturnType> {
        deletion: {
            setDeletion: (attributes: Record<string, string>) => ReturnType;
            unsetDeletion: () => ReturnType;
        };
    }
}
declare const DeletionMark: Mark<any, any>;

declare const FormatChangeMark: Mark<any, any>;

declare const trackChangesPluginKey: PluginKey<any>;

/**
 * Get all tracked changes from the current document state.
 */
declare function getTrackedChanges(editor: Editor): TrackedChangeInfo[];
/**
 * Group tracked changes by changeId (e.g., a replacement has both insertion + deletion
 * with the same changeId).
 */
declare function getGroupedChanges(editor: Editor): Map<string, TrackedChangeInfo[]>;
/**
 * Get the "base text" — the document as it would appear if all pending changes
 * were rejected. (Original text without any insertions, with deletions restored.)
 */
declare function getBaseText(editor: Editor): string;
/**
 * Get the "result text" — the document as it would appear if all pending changes
 * were accepted. (With insertions applied and deletions removed.)
 */
declare function getResultText(editor: Editor): string;
/**
 * Count pending changes.
 */
declare function getPendingChangeCount(editor: Editor): number;

export { type ChangeAuthor, type ChangeMarkAttributes, DeletionMark, FormatChangeMark, InsertionMark, type NodeChangeTracking, TrackChangesExtension, type TrackChangesMode, type TrackChangesOptions, type TrackChangesStorage, type TrackedChangeInfo, getBaseText, getGroupedChanges, getPendingChangeCount, getResultText, getTrackedChanges, trackChangesPluginKey };
