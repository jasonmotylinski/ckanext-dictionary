"""Actions for data dictionary."""
import json
import logging
import ckan.logic as logic

log = logging.getLogger(__name__)

get_action = logic.get_action


def _create_data_dict_table(context):
    """If the dictionary table does not exist, create it."""
    create = {'resource': {'package_id': id},
                'aliases': 'data_dict',
                'fields': [{'id': 'package_id', 'type': 'text'},
                        {'id': 'id', 'type': 'int4'},
                        {'id': 'title', 'type': 'text'},
                        {'id': 'field_name', 'type': 'text'},
                        {'id': 'format', 'type': 'text'},
                        {'id': 'description', 'type': 'text'}]}
    return get_action('datastore_create')(context, create)

def get_data_dictionary_records(context, package_id, resource_id):
    """Get the data dictionary records from the database."""
    data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id': package_id}, 'sort': ['id']}

    log.info("get_data_dictionary_records: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, package_id))
    return get_action('datastore_search')(context, data_dict_dict)['records']

def get_data_dict_resource_id(context):
    """Get the Datastore resource ID for the data_dict table."""
    tables = get_action('datastore_search')(context, {'resource_id': '_table_metadata'})
    
    resource_id=None
    
    for t in tables['records']:
        if t['name'] == "data_dict":
            resource_id = t['alias_of']
            log.info("get_data_dict_resource_id: Found existing data_dictionary DataStore. alias_of: {0}".format(resource_id))
    
    if resource_id is None:
        new_table=_create_data_dict_table(context)
        return new_table['id']

    return resource_id

def update_data_dictionary(context, data):
    """Update the data dictionary records in datastore and the CKAN dataset database."""
    resource_id = get_data_dict_resource_id(context)
    data['resource_id'] = resource_id
    log.info("update_data_dictionary: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, data['package_id']))
    records = get_data_dictionary_records(context, data['package_id'], resource_id)

    for r in records:
        req = {'resource_id': resource_id, 'filters': {'id': r['id']}}
        log.info("update_data_dictionary: Deleting record resource_id: {0} id: {1}".format(resource_id, r['id']))
        get_action('datastore_delete')(context, req)

    if len(data['records']) > 0:
        for i in range(0, len(data['records'])):
                data['records'][i]['id'] = i
                data['records'][i]['package_id']=data['package_id']

        log.info("update_data_dictionary: Update dataset schema for package_id : {0} data: {1}".format(data['package_id'], data))
        update_schema_field(context, data['package_id'], data["records"])

        log.info("update_data_dictionary: Create records for resource_id: {0} data: {1}".format(resource_id, data))
        get_action('datastore_create')(context, data)

def update_schema_field(context, package_id, schema):
    """Update the value of the _schema field the given package."""
    package = get_action('package_show')(context, {"id": package_id})
    
    key_found = False
    for e in package['extras']:
        if e['key'] == '_schema':
            e['value'] = json.dumps({"fields": schema})
            key_found = True
            break

    if not key_found:
        package['extras'].append({'key': '_schema', 'value': json.dumps({"fields": schema})})

    get_action('package_patch')(context, {"id": package_id, "extras": package['extras']})