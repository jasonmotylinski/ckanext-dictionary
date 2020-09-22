"""Summary: Controllers for Dictionary Plugin for CKAN.

Description: Contains BaseDDController contains
shared logic between the multiple controllers. ApiController handles API logic.
DDController contains the UI logic.
"""
import logging
import ckan.lib.helpers as h
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
import ckan.lib.plugins
import ckan.lib.render

from ckan.authz import is_authorized
from ckan.common import _, json, request, c, g, response
from ckan.lib.base import BaseController
from ckan.views import identify_user

log = logging.getLogger(__name__)

render = base.render
abort = base.abort

NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
check_access = logic.check_access
get_action = logic.get_action
tuplize_dict = logic.tuplize_dict
clean_dict = logic.clean_dict
parse_params = logic.parse_params
flatten_to_string_key = logic.flatten_to_string_key

lookup_package_plugin = ckan.lib.plugins.lookup_package_plugin


class BaseDDController(BaseController):
    """Base controller class to manage the UI and API."""
    
    def _create_data_dict_table(self, context):
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

    def get_data_dict_resource_id(self, context):
        """Get the Datastore resource ID for the data_dict table."""
        tables = get_action('datastore_search')(context, {'resource_id': '_table_metadata'})
        
        resource_id=None
        
        for t in tables['records']:
            if t['name'] == "data_dict":
                resource_id = t['alias_of']
                log.info("get_data_dict_resource_id: Found existing data_dictionary DataStore. alias_of: {0}".format(resource_id))
        
        if resource_id is None:
            new_table=self._create_data_dict_table(context)
            return new_table['id']

        return resource_id

    def get_data_dictionary_records(self, context, package_id, resource_id):
        """Get the data dictionary records from the database."""
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id': package_id}, 'sort': ['id']}

        log.info("get_data_dictionary_records: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, package_id))
        return get_action('datastore_search')(context, data_dict_dict)['records']

    def update_schema_field(self, context, package_id, schema):
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

    def update_data_dictionary(self, context, data):
        """Update the data dictionary records in datastore and the CKAN dataset database."""
        resource_id = self.get_data_dict_resource_id(context)
        data['resource_id'] = resource_id
        log.info("update_data_dictionary: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, data['package_id']))
        records = self.get_data_dictionary_records(context, data['package_id'], resource_id)

        for r in records:
            req = {'resource_id': resource_id, 'filters': {'id': r['id']}}
            log.info("update_data_dictionary: Deleting record resource_id: {0} id: {1}".format(resource_id, r['id']))
            get_action('datastore_delete')(context, req)

        if len(data['records']) > 0:
            for i in range(0, len(data['records'])):
                    data['records'][i]['id'] = i
                    data['records'][i]['package_id']=data['package_id']

            log.info("update_data_dictionary: Update dataset schema for package_id : {0} data: {1}".format(data['package_id'], data))
            self.update_schema_field(context, data['package_id'], data["records"])

            log.info("update_data_dictionary: Create records for resource_id: {0} data: {1}".format(resource_id, data))
            get_action('datastore_create')(context, data)


class ApiController(BaseDDController):
    """Controller for API actions."""

    def get_context(self):
        """Context of the API request."""
        identify_user()

        return {'model': model, 
                'user': g.user,
                'author': g.author,
                'ignore_auth': True,
                'auth_user_obj': g.userobj}

    def dictionary_update(self):
        """Update the dictionary for a given package."""
        context=self.get_context()
        log.info("dictionary_update:context:{0}".format(context))
        try:
            if request.method == 'POST':
                check_access('dictionary_update', context)
                log.info("dictionary_update:POST:Content-Type:{0}".format(request.content_type))
                log.info("dictionary_update:request.body:{0}".format(request.body))

                self.update_data_dictionary(context, json.loads(request.body))

                response.status_int = 200
                response.headers['Content-Type'] = "application/json"
                return json.dumps({"success": True})
            else:
                response.status_int = 501
                response.headers['Content-Type'] = "application/json"
                return json.dumps({"success": False ,"error": {"messsage": "Not Implemented"}})
        except NotAuthorized as e:
            response.status_int = 403
            response.headers['Content-Type'] = "application/json"
            log.error("dictionary_update:NotAuthorized: {0}".format(e.message))
            return json.dumps({"success": False ,"error": {"messsage": "NotAuthorized"}})   
        except Exception as e:
            response.status_int = 500
            response.headers['Content-Type'] = "application/json"
            log.error("dictionary_update:Exception: {0}".format(e.message))
            return json.dumps({"success": False ,"error": {"messsage": "Exception"}})   


class DDController(BaseDDController):
    """Controller used for UI logic."""

    def get_context(self):
        """Get the context object used by CKAN actions."""
        return {'model': model,
                'session': model.Session,
                'user': c.user or c.author,
                'auth_user_obj': c.userobj}


    def _resource_form(self, package_type):
        """Backwards compatibility with plugins not inheriting from DefaultDatasetPlugin and not implmenting resource_form."""
        plugin = lookup_package_plugin(package_type)
        if hasattr(plugin, 'resource_form'):
            result = plugin.resource_form()
            if result is not None:
                return result
        return lookup_package_plugin().resource_form()


    def edit_dictionary(self, id, data=None, errors=None):
        """Edit dictionary."""
        context=self.get_context()
        context['for_view']=True
        context['use_cache']=False

        resource_id=self.get_data_dict_resource_id(context)
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id': id}, 'sort': ['id']}

        try:
            pkg_data_dictionary = get_action('datastore_search')(context, data_dict_dict)
            c.pkg_data_dictionary = pkg_data_dictionary['records']
            c.link = str("/dataset/dictionary/new_dict/" + id)
            c.pkg_dict = get_action('package_show')(context, {'id': id})
            c.pkg = context['package']
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read dataset %s') % id)
        return render("package/edit_data_dict.html", extra_vars={'package_id': id})

    def get_row_count_from_params(self):
        """Determine how many form rows are being passed in via HTTP parameters."""
        idx = 0
        while True:
            id = request.params.get("field_{0}".format(idx))
            if id is None or id == '':
                break
            else:
                idx = idx + 1
        log.info("get_row_count_from_params: Row count: {0}".format(idx))
        return idx

    def get_record_from_params(self, package_id, resource_id, row_id):
        """Build a record object from request parameters."""
        varNames = ['field_' + str(row_id), 'type_' + str(row_id), 'description_' + str(row_id), 'title_' + str(row_id), 'format_' + str(row_id)]
        datafield = request.params.get(varNames[0])
        datadesc = request.params.get(varNames[2])
        datatitle = request.params.get(varNames[3])
        dataformat = request.params.get(varNames[4])
        return {'field_name': datafield, 'description': datadesc, "title": datatitle, "format": dataformat}

    def new_data_dictionary(self, id):
        """Update the data dictionary for a given package from the web for."""
        package_id = id  # I'm not usually a fan of reassigning variables for no reason, but there are a lot of IDs floating around in this function so reassigning for clarity

        log.info("new_data_dictionary: Package ID: {0}".format(package_id))

        if request.method == 'POST':
            context = self.get_context()
            resource_id = self.get_data_dict_resource_id(context)

            try:
                rowCount = self.get_row_count_from_params()
                data = {"records": [], "package_id": package_id}
                if rowCount > 0:
                    for i in range(0, rowCount):
                        data['records'].append(self.get_record_from_params(data['package_id'], resource_ids, i))

                    self.update_data_dictionary(context, data)
            except NotFound:
                abort(404, _('Dataset not found'))
            except NotAuthorized:
                abort(401, _('Unauthorized to read dataset %s') % id)

            h.redirect_to(controller='package', action='read', id=id)

    def dictionary(self, id):
        """Render logic for displaying the dictionary for a given package."""

        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'for_view': True,
                   'auth_user_obj': c.userobj, 'use_cache': False}
        data_dict = {'id': id}
        try:
            log.info("dictionary: trying to get the data_dict")
            c.pkg_dict = get_action('package_show')(context, data_dict)
            dataset_type = c.pkg_dict['type'] or 'dataset'
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read dataset %s') % id)

        context = self.get_context()

        resource_id = self.get_data_dict_resource_id(context)
                
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id':id},'sort':['id']}
        pkg_data_dictionary = get_action('datastore_search')(context, data_dict_dict)
        print(pkg_data_dictionary['records'])
        c.pkg_data_dictionary = pkg_data_dictionary['records']

        return render('package/dictionary_display.html', {'dataset_type': dataset_type})
