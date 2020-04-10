import logging
from ckan.lib.base import BaseController
import ckan.lib.helpers as h
from ckan.common import _, json, request, c, g, response
import cgi


import ckan.logic as logic
import ckan.lib.base as base
import ckan.lib.navl.dictization_functions as dict_fns

import ckan.model as model
import ckan.lib.plugins
import ckan.lib.render

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
    """
    Base controller class to manage the UI and API
    """

    def get_context(self):
        """
        Get the context object used by CKAN actions
        """
        return {'model': model,
                'session': model.Session,
                'user': c.user or c.author,
                'auth_user_obj': c.userobj}

    def get_data_dict_resource_id(self):
        """
        Get the Datastore resource ID for the data_dict tables
        """
        context = self.get_context()
        tables = get_action('datastore_search')(context, {'resource_id': '_table_metadata'})
        for t in tables['records']:
            if t['name'] == "data_dict":
                resource_id = t['alias_of']
                log.info("get_data_dict_table: Found existing data_dictionary DataStore. alias_of: {0}".format(resource_id))
                return resource_id
        return None

    def get_data_dictionary_records(self, package_id, resource_id):
        """
        Get the data dictionary records from the database
        """
        context = self.get_context()
        data_dict_dict = {'resource_id': resource_id, 'filters': {'package_id': package_id}, 'sort': ['id']}

        log.info("get_data_dictionary_records: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, package_id))
        return get_action('datastore_search')(context, data_dict_dict)['records']
    
    def update_data_dictionary(self, data):
        """
        Update the data dictionary records in datastore and the CKAN dataset database
        """
        context = self.get_context()
        resource_id = self.get_data_dict_resource_id()
        log.info("update_data_dictionary: Getting records for resource_id: {0} and package_id: {1}".format(resource_id, data['package_id']))
        records = self.get_data_dictionary_records(data['package_id'], resource_id)

        for r in records:
            req = {'resource_id': resource_id, 'filters': {'id': r['id']}}
            log.info("update_data_dictionary: Deleting record resource_id: {0} id: {1}".format(resource_id, r['id']))
            get_action('datastore_delete')(context, req)

        if len(data['records']) > 0:
            data = {'resource_id': resource_id, 'records': []}

            log.info("update_data_dictionary: Update dataset schema for package_id : {0} data: {1}".format(data['package_id'], data))
            self.update_schema_field(context, data['package_id'], data["records"])

            log.info("update_data_dictionary: Create records for resource_id: {0} data: {1}".format(resource_id, data))
            get_action('datastore_create')(context, data)

   
class ApiController(BaseDDController):
    """Controller for API actions"""

    def dictionary_update(self):
        """Update the dictionary for a given package"""
        if request.method == 'POST':
            body = json.load(request.data)
            self.update_data_dictionary(body)
            response.headers['Content-Type'] = "application/json"
            return json.dumps({"json": "yes"})
        else:
            response.status_int = 501
            response.headers['Content-Type'] = "application/json"
            return json.dumps({"error": "Not Implemented"})


class DDController(BaseDDController):

    def _resource_form(self, package_type):
        # backwards compatibility with plugins not inheriting from
        # DefaultDatasetPlugin and not implmenting resource_form
        plugin = lookup_package_plugin(package_type)
        if hasattr(plugin, 'resource_form'):
            result = plugin.resource_form()
            if result is not None:
                return result
        return lookup_package_plugin().resource_form()

    def finaldict(self, id, data=None, errors=None):
        c.link = "/dataset/dictionary/new_dict/{0}".format(str(id))
        return render("package/new_data_dict.html", extra_vars={'package_id': str(id)})

    def edit_dictionary(self, id, data=None, errors=None):
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'for_view': True,
                   'auth_user_obj': c.userobj, 'use_cache': False}

        resource_ids = None

        meta_dict = {'resource_id': '_table_metadata'}
        tables = get_action('datastore_search')(context, meta_dict)
        for t in tables['records']:
            if t['name'] == "data_dict":
                resource_ids = t['alias_of']

        if resource_ids is None:
            create = {'resource': {'package_id': id},
                      'aliases': 'data_dict',
                      'fields': [{'id': 'package_id', 'type': 'text'},
                                 {'id': 'id', 'type': 'int4'},
                                 {'id': 'title', 'type': 'text'},
                                 {'id': 'field_name', 'type': 'text'},
                                 {'id': 'format', 'type': 'text'},
                                 {'id': 'description', 'type': 'text'}]}
            get_action('datastore_create')(context, create)
            meta_dict = {'resource_id': '_table_metadata'}
            tables = get_action('datastore_search')(context, meta_dict)
            for t in tables['records']:
                print(t['name'])
                if t['name'] == "data_dict":
                    resource_ids = t['alias_of']

        data_dict_dict = {'resource_id': resource_ids, 'filters': {'package_id': id}, 'sort': ['id']}

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

    def redirectSecond(self, id, data=None, errors=None):
        return render("package/new_resource.html")

    def update_schema_field(self, context, package_id, schema):
        package = get_action('package_show')(context, {"id": package_id})
      
        key_found = False
        for e in package['extras']:
            if e['key'] == '_schema':
                e['value'] = json.dumps({"fields": schema})
                key_found = True
                break

        if not key_found:
            e['extras'].append({'key': '_schema', 'value': json.dumps({"fields": schema})})

        get_action('package_patch')(context, {"id": package_id, "extras": package['extras']})

    def get_row_count_from_params(self):
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
        varNames = ['field_' + str(row_id), 'type_' + str(row_id), 'description_' + str(row_id), 'title_' + str(row_id), 'format_' + str(row_id)]
        datafield = request.params.get(varNames[0])
        datadesc = request.params.get(varNames[2])
        datatitle = request.params.get(varNames[3])
        dataformat = request.params.get(varNames[4])
        return {'package_id': package_id, 'field_name': datafield, 'description': datadesc, "title": datatitle, "format": dataformat, "id": str(row_id)}

    def new_data_dictionary(self, id):
        package_id = id  # I'm not usually a fan of reassigning variables for no reason, but there are a lot of IDs floating around in this function so reassigning for clarity
        
        log.info("new_data_dictionary: Package ID: {0}".format(package_id))

        if request.method == 'POST':
            context = self.get_context()
            resource_ids = self.get_data_dict_resource_id()

            if resource_ids is None:
                log.info("new_data_dictionary: data_dict not found in DataStore. Creating")
                create = {'resource': {'package_id': id},
                          'aliases': 'data_dict',
                          'fields': [{'id': 'package_id', 'type': 'text'},
                                     {'id': 'id', 'type': 'int4'},
                                     {'id': 'title', 'type': 'text'},
                                     {'id': 'field_name', 'type': 'text'},
                                     {'id': 'format', 'type': 'text'},
                                     {'id': 'description', 'type': 'text'}]}
                get_action('datastore_create')(context, create)
                meta_dict = {'resource_id': '_table_metadata'}
                tables = get_action('datastore_search')(context, meta_dict)
                for t in tables['records']:
                    if t['name'] == "data_dict":
                        resource_ids = t['alias_of']

            try:
                rowCount = self.get_row_count_from_params()
                data = {"records": [], "package_id": package_id}
                if rowCount > 0:
                    for i in range(0, rowCount):
                        data['records'].append(self.get_record_from_params(data['package_id'], resource_ids, i))

                    self.update_data_dictionary(data)
            except NotFound:
                abort(404, _('Dataset not found'))
            except NotAuthorized:
                abort(401, _('Unauthorized to read dataset %s') % id)

            h.redirect_to(controller='package', action='read', id=id)

    def new_resource_ext(self, id, data=None, errors=None, error_summary=None):
        ''' FIXME: This is a temporary action to allow styling of the
        forms. '''
        c.linkResource = str("/dataset/new_resource/" + id)
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! IN NEW_RESOURCE_EXT !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        if request.method == 'POST' and not data:
            save_action = request.params.get('save')

            data = data or \
                clean_dict(dict_fns.unflatten(tuplize_dict(parse_params(
                                                           request.POST))))
            # we don't want to include save as it is part of the form
            del data['save']
            resource_id = data['id']

            del data['id']

            context = {'model': model, 'session': model.Session,
                       'user': c.user or c.author, 'auth_user_obj': c.userobj}

            # see if we have any data that we are trying to save

            data_provided = False
            for key, value in data.iteritems():
                if ((value or isinstance(value, cgi.FieldStorage))
                        and key != 'resource_type'):
                    data_provided = True
                    break
            if not data_provided and save_action != "go-dataset-complete":
                if save_action == 'go-dataset':
                    # go to final stage of adddataset
                    h.redirect_to(controller='package',
                                  action='edit', 
                                  id=id)
                # see if we have added any resources
                try:
                    data_dict = get_action('package_show')(context, {'id': id})
                except NotAuthorized:
                    abort(401, _('Unauthorized to update dataset'))
                except NotFound:
                    abort(404, _('The dataset {id} could not be found.'
                                 ).format(id=id))
                if not len(data_dict['resources']):
                    # no data so keep on page
                    msg = _('You must add at least one data resource')
                    # On new templates do not use flash message
                    if g.legacy_templates:
                        h.flash_error(msg)
                        h.redirect_to(controller='package',
                                           action='new_resource', id=id)
                    else:
                        errors = {}
                        error_summary = {_('Error'): msg}
                        return self.new_resource_ext(id, data, errors,
                                                 error_summary)
                # XXX race condition if another user edits/deletes
                data_dict = get_action('package_show')(context, {'id': id})
                get_action('package_update')(
                    dict(context, allow_state_change=True),
                    dict(data_dict, state='active'))
                h.redirect_to(controller='package',
                                   action='read', id=id)

            data['package_id'] = id
            try:
                if resource_id:
                    data['id'] = resource_id
                    get_action('resource_update')(context, data)
                else:
                    get_action('resource_create')(context, data)
            except ValidationError, e:
                errors = e.error_dict
                error_summary = e.error_summary
                return self.new_resource(id, data, errors, error_summary)
            except NotAuthorized:
                abort(401, _('Unauthorized to create a resource'))
            except NotFound:
                abort(404, _('The dataset {id} could not be found.'
                             ).format(id=id))
            if save_action == 'go-metadata':
                # XXX race condition if another user edits/deletes
                data_dict = get_action('package_show')(context, {'id': id})
                get_action('package_update')(
                    dict(context, allow_state_change=True),
                    dict(data_dict, state='active'))
                h.redirect_to(controller='package',
                                   action='read', id=id)
            elif save_action == 'go-datadict':
                print('save action was go-datadict in the exntenstion NEEWWWW!!!!!!!!!!!')
                h.redirect_to(str("/dataset/dictionary/add/"+id))
            elif save_action == 'go-dataset':
                # go to first stage of add dataset
                h.redirect_to(controller='package',
                                   action='edit', id=id)
            elif save_action == 'go-dataset-complete':
                # go to first stage of add dataset
                h.redirect_to(controller='package',
                                   action='read', id=id)
            else:
                # add more resources
                h.redirect_to(controller='package',
                                   action='new_resource', id=id)

        # get resources for sidebar
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'auth_user_obj': c.userobj}
        try:
            pkg_dict = get_action('package_show')(context, {'id': id})
        except NotFound:
            abort(404, _('The dataset {id} could not be found.').format(id=id))
        try:
            check_access(
                'resource_create', context, {"package_id": pkg_dict["id"]})
        except NotAuthorized:
            abort(401, _('Unauthorized to create a resource for this package'))

        package_type = pkg_dict['type'] or 'dataset'

        errors = errors or {}
        error_summary = error_summary or {}
        vars = {'data': data, 'errors': errors,
                'error_summary': error_summary, 'action': 'new',
                'resource_form_snippet': self._resource_form(package_type),
                'dataset_type': package_type}
        vars['pkg_name'] = id
        # required for nav menu
        vars['pkg_dict'] = pkg_dict
        template = 'package/new_resource_not_draft.html'
        if pkg_dict['state'].startswith('draft'):
            vars['stage'] = ['complete', 'active']
            template = 'package/new_resource.html'
        return render(template, extra_vars=vars)
    
    def dictionary(self, id):
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

        resource_ids = None
        try:
            meta_dict = {'resource_id': '_table_metadata'}
            tables = get_action('datastore_search')(context, meta_dict)
            for t in tables['records']:
                print(t['name'])
                if t['name'] == "data_dict":
                    resource_ids = t['alias_of']
        except:
            resource_ids = None
            if resource_ids == None:
                create = {'resource':{'package_id':id},'aliases':'data_dict','fields':[{'id':'package_id','type':'text'},{'id':'id','type':'int4'},{'id':'title','type':'text'},{'id':'field_name','type':'text'},{'id':'format','type':'text'},{'id':'description','type':'text'}]}
                log.info("dictionary: creating the data_dict table in the datastore")
                get_action('datastore_create')(context, create)
                
                meta_dict = {'resource_id': '_table_metadata'}
                tables = get_action('datastore_search')(context, meta_dict)
                for t in tables['records']:
                    print(t['name'])
                    if t['name'] == "data_dict":
                        resource_ids = t['alias_of']
        data_dict_dict = {'resource_id': resource_ids, 'filters': {'package_id':id},'sort':['id']}

        try:
            pkg_data_dictionary = get_action('datastore_search')(context, data_dict_dict)
            print(pkg_data_dictionary['records'])
            c.pkg_data_dictionary = pkg_data_dictionary['records']
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read dataset %s') % id)
        return render('package/dictionary_display.html',{'dataset_type': dataset_type})
